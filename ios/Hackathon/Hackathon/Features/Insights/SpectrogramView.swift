//
//  SpectrogramView.swift
//  Hackathon
//
//  Downloads a track's 30s preview, decodes it, runs MelSpectrogram over it
//  and renders the frames as a heatmap (time ->, low frequencies at the
//  bottom). A playhead line rides the shared PlaybackController's progress
//  when this track is the one playing.
//

import AVFoundation
import SwiftUI

@MainActor
@Observable
final class SpectrogramLoader {
    private(set) var image: CGImage?
    private(set) var isLoading = false
    private(set) var loadedTrackID: String?

    private let resolver: PreviewResolver

    init(resolver: PreviewResolver = .shared) {
        self.resolver = resolver
    }

    func load(_ track: Track) async {
        guard loadedTrackID != track.trackID else { return }
        loadedTrackID = track.trackID
        image = nil
        isLoading = true
        defer { isLoading = false }

        guard let url = await resolver.previewURL(for: track),
              let samples = try? await Self.samples(from: url) else { return }
        let rendered = await Self.render(samples: samples.data,
                                         sampleRate: samples.rate)
        // A newer request may have superseded this one while we computed.
        if loadedTrackID == track.trackID { image = rendered }
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

    private nonisolated static func render(samples: [Float],
                                           sampleRate: Double) async -> CGImage? {
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
        guard let context = CGContext(
            data: &pixels, width: width, height: height, bitsPerComponent: 8,
            bytesPerRow: width * 4, space: space, bitmapInfo: info
        ) else { return nil }
        return context.makeImage()
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
    @Environment(PlaybackController.self) private var playback

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Mel-spectrogram — \(track.title)")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            ZStack {
                RoundedRectangle(cornerRadius: 8).fill(.black)
                if let image = loader.image {
                    GeometryReader { proxy in
                        Image(decorative: image, scale: 1)
                            .resizable()
                            .interpolation(.medium)
                        if playback.nowPlayingID == track.trackID {
                            Rectangle()
                                .fill(.white.opacity(0.9))
                                .frame(width: 1.5)
                                .offset(x: proxy.size.width * playback.progress)
                        }
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
            .frame(height: 140)
        }
        .task(id: track.trackID) { await loader.load(track) }
    }
}
