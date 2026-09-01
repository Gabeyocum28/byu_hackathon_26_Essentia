//
//  SpectrogramView.swift
//  Hackathon
//
//  Downloads a track's 30s preview, decodes it, runs MelSpectrogram over it
//  and renders the frames as a heatmap (time ->, low frequencies at the
//  bottom). A playhead line rides the shared PlaybackController's progress
//  when this track is the one playing.
//
//  Also hosts two on-device T2 features composed into the same screen:
//   - T2.3 self-similarity ("recurrence") matrix, below the spectrogram —
//     tap a block to jump.
//   - T2.5 band-solo — drag the slim strip on the spectrogram's leading
//     edge to pick a frequency band, tap SOLO to hear an STFT-mask
//     resynthesis of just that band.
//

import AVFoundation
import SwiftUI

@MainActor
@Observable
final class SpectrogramLoader {
    private(set) var image: CGImage?
    private(set) var similarityImage: CGImage?
    private(set) var isLoading = false
    private(set) var loadedTrackID: String?
    /// bands+2 Hz filterbank edges from the render pass, for mapping a
    /// selected band range to Hz (see MelSpectrogram.hzRange(forBands:)).
    private(set) var bandEdgesHz: [Double] = []
    private(set) var bands: Int = 0

    private var samples: [Float] = []
    private var sampleRate: Double = 0
    /// Built lazily on the first band-solo request; ~10MB for a 30s preview,
    /// not worth computing unless the feature is actually used.
    private var stftCache: STFTComplex?

    private let resolver: PreviewResolver

    init(resolver: PreviewResolver = .shared) {
        self.resolver = resolver
    }

    func load(_ track: Track) async {
        guard loadedTrackID != track.trackID else { return }
        loadedTrackID = track.trackID
        image = nil
        similarityImage = nil
        bandEdgesHz = []
        bands = 0
        samples = []
        sampleRate = 0
        stftCache = nil
        isLoading = true
        defer { isLoading = false }

        guard let url = await resolver.previewURL(for: track),
              let decoded = try? await Self.samples(from: url) else { return }
        let rendered = await Self.render(samples: decoded.data, sampleRate: decoded.rate)
        // A newer request may have superseded this one while we computed.
        guard loadedTrackID == track.trackID else { return }
        image = rendered?.image
        similarityImage = rendered?.similarityImage
        bandEdgesHz = rendered?.bandEdgesHz ?? []
        bands = rendered?.bands ?? 0
        samples = decoded.data
        sampleRate = decoded.rate
    }

    /// Hz span for a selected band index range, from the exact filterbank
    /// edges the rendered spectrogram used.
    func hzRange(forBands range: ClosedRange<Int>) -> (lo: Double, hi: Double)? {
        guard bands > 0, bandEdgesHz.count == bands + 2 else { return nil }
        let lo = bandEdgesHz[max(0, min(range.lowerBound, bands - 1))]
        let hi = bandEdgesHz[max(0, min(range.upperBound, bands - 1)) + 2]
        return (lo, hi)
    }

    /// Resynthesizes just `loHz...hiHz` of this track's audio via STFT-mask
    /// band-solo (T2.5), building (and caching) the complex STFT on first
    /// use. Returns nil if the track hasn't finished loading.
    func soloBuffer(loHz: Double, hiHz: Double) async -> (samples: [Float], sampleRate: Double)? {
        let requestID = loadedTrackID
        guard let stft = await stft() else { return nil }
        let built = await Self.resynthesize(stft: stft, loHz: loHz, hiHz: hiHz)
        // A newer track may have loaded while this computed.
        guard loadedTrackID == requestID else { return nil }
        return built
    }

    private func stft() async -> STFTComplex? {
        if let stftCache { return stftCache }
        guard !samples.isEmpty, sampleRate > 0 else { return nil }
        let requestID = loadedTrackID
        let built = await Self.buildSTFT(samples: samples, sampleRate: sampleRate)
        guard loadedTrackID == requestID else { return nil }
        stftCache = built
        return built
    }

    // MARK: - Decode

    private static func samples(from url: URL) async throws -> (data: [Float], rate: Double) {
        let (localURL, _) = try await URLSession.shared.download(from: url)
        // AVAudioFile wants a recognizable extension for mp3 previews.
        let mp3URL = localURL.deletingPathExtension().appendingPathExtension("mp3")
        try? FileManager.default.moveItem(at: localURL, to: mp3URL)
        defer { try? FileManager.default.removeItem(at: mp3URL) }

        // read(into:) insists on the file's own processing format (stereo for
        // Deezer previews) — asking for mono up front fails with -50. Read
        // native, then average the channels down.
        let file = try AVAudioFile(forReading: mp3URL)
        let format = file.processingFormat
        let frames = AVAudioFrameCount(file.length)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format,
                                            frameCapacity: frames) else {
            throw APIError.invalidResponse
        }
        try file.read(into: buffer)
        guard let channels = buffer.floatChannelData else {
            throw APIError.invalidResponse
        }
        let count = Int(buffer.frameLength)
        let channelCount = Int(format.channelCount)
        var mono = [Float](repeating: 0, count: count)
        for c in 0..<channelCount {
            let channel = channels[c]
            let gain = 1 / Float(channelCount)
            for i in 0..<count { mono[i] += channel[i] * gain }
        }
        return (mono, format.sampleRate)
    }

    // MARK: - Render

    // @concurrent: with default-MainActor isolation plus approachable
    // concurrency, a plain nonisolated async func would still run on the
    // caller's (main) actor — this FFT pass must actually leave the main
    // thread or the whole screen hitches while a spectrogram computes.
    @concurrent
    private static func render(
        samples: [Float], sampleRate: Double
    ) async -> (image: CGImage?, similarityImage: CGImage?, bandEdgesHz: [Double], bands: Int)? {
        let spectrogram = MelSpectrogram(bands: 96, sampleRate: sampleRate,
                                         fftSize: 2048, hop: 1024)
        let frames = spectrogram.compute(samples: samples)
        guard !frames.isEmpty else { return nil }

        let width = frames.count
        let height = spectrogram.bands
        // dB values are relative to an arbitrary FFT scale, so anchor the top
        // of the colormap at the track's own loudest moment.
        let peak = frames.reduce(-Float.greatestFiniteMagnitude) {
            max($0, $1.max() ?? -Float.greatestFiniteMagnitude)
        }
        let range: Float = 70
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        for (col, frame) in frames.enumerated() {
            for band in 0..<height {
                // Row 0 is the top of the image = highest band.
                let row = height - 1 - band
                let t = (frame[band] - peak + range) / range
                let (r, g, b) = heat(CGFloat(max(0, min(1, t))))
                let idx = (row * width + col) * 4
                pixels[idx] = UInt8(r * 255)
                pixels[idx + 1] = UInt8(g * 255)
                pixels[idx + 2] = UInt8(b * 255)
                pixels[idx + 3] = 255
            }
        }

        let space = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        let image = CGContext(
            data: &pixels, width: width, height: height, bitsPerComponent: 8,
            bytesPerRow: width * 4, space: space, bitmapInfo: info
        )?.makeImage()

        let similarity = SelfSimilarityMatrix(frames: frames)
        let similarityImage = similarity.image(colormap: heat)

        return (image, similarityImage, spectrogram.bandEdgesHz, spectrogram.bands)
    }

    @concurrent
    private static func buildSTFT(samples: [Float], sampleRate: Double) async -> STFTComplex? {
        STFTComplex(samples: samples, sampleRate: sampleRate, fftSize: 2048, hop: 1024)
    }

    @concurrent
    private static func resynthesize(
        stft: STFTComplex, loHz: Double, hiHz: Double
    ) async -> (samples: [Float], sampleRate: Double) {
        let a = stft.bin(forHz: loHz)
        let b = stft.bin(forHz: hiHz)
        let mask = BandSoloMask.raisedCosine(bins: stft.bins, loBin: min(a, b),
                                             hiBin: max(a, b), taperBins: 4)
        return (stft.resynthesize(mask: mask), stft.sampleRate)
    }

    /// Black -> deep purple -> magenta -> orange -> near-white, inferno-ish.
    private nonisolated static func heat(_ t: CGFloat) -> (CGFloat, CGFloat, CGFloat) {
        let stops: [(CGFloat, CGFloat, CGFloat)] = [
            (0.00, 0.00, 0.02), (0.20, 0.03, 0.35), (0.55, 0.10, 0.42),
            (0.90, 0.35, 0.15), (0.99, 0.75, 0.20), (0.99, 0.98, 0.80),
        ]
        let scaled = t * CGFloat(stops.count - 1)
        let i = min(Int(scaled), stops.count - 2)
        let f = scaled - CGFloat(i)
        let (r0, g0, b0) = stops[i], (r1, g1, b1) = stops[i + 1]
        return (r0 + (r1 - r0) * f, g0 + (g1 - g0) * f, b0 + (b1 - b0) * f)
    }
}

struct SpectrogramView: View {
    let track: Track
    @State private var loader = SpectrogramLoader()
    @State private var draggedProgress: Double?

    // T2.5 band-solo state.
    @State private var selectedBandRange: ClosedRange<Int>?
    @State private var bandDragStart: Int?
    @State private var bandSoloPlayer = BandSoloPlayer()
    @State private var isBuildingSolo = false

    @Environment(PlaybackController.self) private var playback

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Mel-spectrogram — \(track.title)")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            spectrogramBody
                .frame(height: 140)
            if selectedBandRange != nil {
                soloControls
            }
            if loader.similarityImage != nil {
                Text("Self-similarity — tap a block to jump")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                similarityBody
                    .frame(height: 160)
            }
        }
        .task(id: track.trackID) { await loader.load(track) }
        .onChange(of: track.trackID) {
            selectedBandRange = nil
            bandDragStart = nil
            bandSoloPlayer.stop()
        }
    }

    // MARK: - Spectrogram + band-select strip

    private var spectrogramBody: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8).fill(.black)
            if let image = loader.image {
                HStack(spacing: 1) {
                    bandSelectStrip
                        .frame(width: 16)
                    spectrogramImage(image)
                }
                .clipShape(.rect(cornerRadius: 8))
            } else if loader.isLoading {
                ProgressView().tint(.white)
            } else {
                Text("No preview audio")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func spectrogramImage(_ image: CGImage) -> some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Image(decorative: image, scale: 1)
                    .resizable()
                    .interpolation(.medium)
                if playback.nowPlayingID == track.trackID {
                    Rectangle()
                        .fill(.white.opacity(0.9))
                        .frame(width: 1.5)
                        .offset(x: proxy.size.width * (draggedProgress ?? playback.progress))
                }
                if let range = selectedBandRange, loader.bands > 0 {
                    bandHighlight(range, height: proxy.size.height)
                }
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        let progress = value.location.x / max(proxy.size.width, 1)
                        let clamped = min(max(progress, 0), 1)
                        draggedProgress = clamped
                        playback.seek(progress: clamped)
                    }
                    .onEnded { value in
                        let progress = value.location.x / max(proxy.size.width, 1)
                        playback.seek(progress: min(max(progress, 0), 1))
                        draggedProgress = nil
                    }
            )
        }
    }

    /// A slim leading-edge affordance, separate from the spectrogram's own
    /// horizontal scrub gesture: a vertical drag here picks a frequency band
    /// range (highlighted back on the spectrogram) instead of seeking.
    private var bandSelectStrip: some View {
        GeometryReader { proxy in
            ZStack {
                Rectangle().fill(.white.opacity(0.06))
                if let range = selectedBandRange, loader.bands > 0 {
                    bandHighlight(range, height: proxy.size.height)
                }
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        guard loader.bands > 0 else { return }
                        let band = bandIndex(atY: value.location.y, height: proxy.size.height)
                        if bandDragStart == nil { bandDragStart = band }
                        let start = bandDragStart ?? band
                        selectedBandRange = min(start, band)...max(start, band)
                    }
                    .onEnded { _ in bandDragStart = nil }
            )
        }
    }

    private func bandIndex(atY y: CGFloat, height: CGFloat) -> Int {
        let fraction = min(max(y / max(height, 1), 0), 1)
        let band = Int(((1 - fraction) * Double(loader.bands - 1)).rounded())
        return min(max(band, 0), loader.bands - 1)
    }

    /// Highlight rectangle spanning the selected band range's vertical
    /// slice of the (bands-tall, image-coordinate) spectrogram.
    private func bandHighlight(_ range: ClosedRange<Int>, height: CGFloat) -> some View {
        let bands = Double(loader.bands)
        let top = (bands - 1 - Double(range.upperBound)) / bands
        let bottom = (bands - Double(range.lowerBound)) / bands
        return Rectangle()
            .fill(.yellow.opacity(0.28))
            .frame(height: height * (bottom - top))
            .frame(maxHeight: .infinity, alignment: .top)
            .offset(y: height * top)
            .allowsHitTesting(false)
    }

    private var soloControls: some View {
        HStack(spacing: 8) {
            Button(action: toggleSolo) {
                HStack(spacing: 4) {
                    if isBuildingSolo {
                        ProgressView().controlSize(.small)
                    } else {
                        Image(systemName: bandSoloPlayer.isPlaying ? "stop.fill" : "play.fill")
                    }
                    Text(soloLabel)
                }
                .font(.caption.weight(.semibold))
            }
            .buttonStyle(.bordered)
            .disabled(isBuildingSolo)
            Spacer()
        }
    }

    private var soloLabel: String {
        guard let range = selectedBandRange, let hz = loader.hzRange(forBands: range) else {
            return "SOLO"
        }
        let lo = Int(hz.lo.rounded()), hi = Int(hz.hi.rounded())
        return bandSoloPlayer.isPlaying ? "STOP \(lo)–\(hi) Hz" : "SOLO \(lo)–\(hi) Hz"
    }

    private func toggleSolo() {
        guard let range = selectedBandRange else { return }
        if bandSoloPlayer.isPlaying {
            bandSoloPlayer.stop()
            return
        }
        guard let hz = loader.hzRange(forBands: range) else { return }
        // Band-solo owns audio output while it plays; the shared preview
        // yields rather than fighting it for the AVAudioSession.
        playback.pause()
        isBuildingSolo = true
        Task {
            let result = await loader.soloBuffer(loHz: hz.lo, hiHz: hz.hi)
            isBuildingSolo = false
            guard let result else { return }
            bandSoloPlayer.play(samples: result.samples, sampleRate: result.sampleRate)
        }
    }

    // MARK: - Self-similarity matrix

    private var similarityBody: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8).fill(.black)
            if let image = loader.similarityImage {
                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        Image(decorative: image, scale: 1)
                            .resizable()
                            .interpolation(.none)
                        if playback.nowPlayingID == track.trackID {
                            Rectangle()
                                .fill(.white.opacity(0.9))
                                .frame(width: 1.5)
                                .offset(x: proxy.size.width * (draggedProgress ?? playback.progress))
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture { location in
                        let progress = location.x / max(proxy.size.width, 1)
                        playback.seek(progress: min(max(progress, 0), 1))
                    }
                }
                .clipShape(.rect(cornerRadius: 8))
            }
        }
    }
}
