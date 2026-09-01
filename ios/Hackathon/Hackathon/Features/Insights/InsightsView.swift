//
//  InsightsView.swift
//  Hackathon
//
//  The wow screen: where the corpus lies (galaxy map of embedding space), what
//  the playing track looks like (mel-spectrogram), and the actual arithmetic
//  behind the selected recommendation's score.
//

import SwiftUI

enum InsightMode: String, CaseIterable, Identifiable {
    case galaxy = "Galaxy"
    case sound = "Sound"
    case proof = "Proof"

    var id: String { rawValue }
}

enum GalaxyMode: String, CaseIterable, Identifiable {
    case explore = "Explore"
    case walk = "Walk"

    var id: String { rawValue }
}

struct WalkEndpoints: Equatable {
    let from: String
    let to: String
}

@MainActor
@Observable
final class InsightsModel {
    let seed: Track
    let axis: Axis
    var map: VizMap?
    var proofMap: VizMap?
    var selected: VizMap.Rec?
    var focusedPoint: GalaxySelection?
    var mode: InsightMode = .galaxy
    var galaxyMode: GalaxyMode = .explore
    var walkStart: GalaxySelection?
    var walk: VizWalk?
    var walkProgress: CGFloat = 0
    var histogram: VizHistogram?
    var hubs: VizHubs?
    var correctionEnabled = true
    var isLoading = true
    var errorMessage: String?
    var proofError: String?

    private let api: APIClient

    init(seed: Track, axis: Axis, api: APIClient = .shared) {
        self.seed = seed
        self.axis = axis
        self.api = api
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            let map = try await api.vizMap(trackID: seed.trackID, axis: axis.id)
            self.map = map
            selected = map.recs.first
            if let rec = map.recs.first {
                focusedPoint = GalaxySelection(track: rec.track, x: rec.x, y: rec.y)
            }
            histogram = try? await api.vizHistogram(trackID: seed.trackID)
            hubs = try? await api.vizHubs()
            proofMap = try? await api.vizMap(
                trackID: seed.trackID, axis: "surprise", correction: true
            )
        } catch {
            errorMessage = "The math needs an analyzed corpus — is the server up?"
        }
        isLoading = false
    }

    /// One intent keeps the visual selection and audible selection together.
    func selectAndPlay(_ rec: VizMap.Rec, play: (Track) -> Void) {
        selected = rec
        focusedPoint = GalaxySelection(track: rec.track, x: rec.x, y: rec.y)
        play(rec.track)
    }

    func focus(_ point: GalaxySelection) {
        focusedPoint = point
        let source = mode == .proof ? proofMap : map
        if let rec = source?.recs.first(where: { $0.trackID == point.id }) {
            selected = rec
        }
    }

    func focus(_ track: Track) {
        guard let map = displayMap,
              let index = map.points.ids.firstIndex(of: track.trackID) else { return }
        focus(GalaxySelection(track: track, x: map.points.x[index],
                              y: map.points.y[index]))
    }

    var displayMap: VizMap? {
        mode == .proof ? (proofMap ?? map) : map
    }

    func activate(_ mode: InsightMode) {
        self.mode = mode
        let source = displayMap
        if let rec = source?.recs.first {
            selected = rec
            focusedPoint = GalaxySelection(track: rec.track, x: rec.x, y: rec.y)
        }
    }

    func setGalaxyMode(_ mode: GalaxyMode) {
        galaxyMode = mode
        walkStart = nil
        if mode == .explore {
            walk = nil
            walkProgress = 0
        }
    }

    /// First tap arms the walk; the second distinct tap yields the request.
    func selectWalkPoint(_ point: GalaxySelection) -> WalkEndpoints? {
        if walkStart?.id == point.id { return nil }
        guard let start = walkStart else {
            walkStart = point
            return nil
        }
        walkStart = nil
        return WalkEndpoints(from: start.id, to: point.id)
    }

    func selectGalaxyPoint(_ point: GalaxySelection) async {
        focus(point)
        guard galaxyMode == .walk,
              let endpoints = selectWalkPoint(point) else { return }
        do {
            walk = try await api.vizWalk(from: endpoints.from, to: endpoints.to)
            walkProgress = 0
            withAnimation(.easeInOut(duration: max(0.8, Double(walk?.path.count ?? 1) * 0.22))) {
                walkProgress = 1
            }
        } catch {
            proofError = "No connected walk for that pair. Try two closer stars."
        }
    }

    func setCorrection(_ enabled: Bool) async {
        correctionEnabled = enabled
        do {
            let updated = try await api.vizMap(
                trackID: seed.trackID, axis: "surprise", correction: enabled
            )
            withAnimation(.spring(duration: 0.45)) {
                proofMap = updated
                selected = updated.recs.first
                if let rec = updated.recs.first {
                    focusedPoint = GalaxySelection(track: rec.track, x: rec.x, y: rec.y)
                }
            }
            proofError = nil
        } catch {
            correctionEnabled.toggle()
            proofError = "The correction comparison could not be loaded."
        }
    }
}

struct InsightsView: View {
    @State private var model: InsightsModel
    @Environment(PlaybackController.self) private var playback

    init(seed: Track, axis: Axis) {
        _model = State(initialValue: InsightsModel(seed: seed, axis: axis))
    }

    var body: some View {
        Group {
            if let errorMessage = model.errorMessage {
                RetryView(message: errorMessage) {
                    Task { await model.load() }
                }
            } else if let map = model.map {
                loaded(map)
            } else {
                ProgressView("Projecting \u{2026}")
            }
        }
        .navigationTitle("The Math")
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load() }
    }

    private func loaded(_ map: VizMap) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Picker("Insight mode", selection: $model.mode) {
                    ForEach(InsightMode.allCases) { mode in
                        Text(mode.rawValue.uppercased()).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .onChange(of: model.mode) { _, mode in model.activate(mode) }

                switch model.mode {
                case .galaxy:
                    galaxyMode(map)
                case .sound:
                    soundMode(map)
                case .proof:
                    proofMode(model.proofMap ?? map)
                }

                recPicker(model.displayMap ?? map)
            }
            .padding()
        }
    }

    private func galaxyMode(_ map: VizMap) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Galaxy interaction", selection: $model.galaxyMode) {
                ForEach(GalaxyMode.allCases) { mode in Text(mode.rawValue).tag(mode) }
            }
            .pickerStyle(.segmented)
            .onChange(of: model.galaxyMode) { _, mode in model.setGalaxyMode(mode) }

            Text(model.galaxyMode == .walk
                 ? (model.walkStart == nil ? "Tap a start star" : "Tap a destination star")
                 : "\(map.points.ids.count) tracks · pinch, pan, tap any star")
                .font(.caption)
                .foregroundStyle(.secondary)

            GalaxyMapView(
                map: map,
                selectedTrackID: model.focusedPoint?.id,
                walk: model.walk,
                walkProgress: model.walkProgress,
                onSelect: { point in Task { await model.selectGalaxyPoint(point) } }
            )
            .aspectRatio(1, contentMode: .fit)
            .background(.black, in: .rect(cornerRadius: 12))

            if let point = model.focusedPoint { galaxyCallout(point) }
            if let walk = model.walk {
                WalkStrip(walk: walk) { step in
                    let point = GalaxySelection(track: step.track, x: step.x, y: step.y)
                    model.focus(point)
                    playback.toggle(step.track)
                }
            }
        }
    }

    private func soundMode(_ map: VizMap) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            SpectrogramView(track: spotlightTrack(map))
            if let rec = model.selected {
                MathPanel(seed: map.seed, rec: rec, axis: map.axis)
            }
        }
    }

    private func proofMode(_ map: VizMap) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            ProofModeView(
                map: map,
                histogram: model.histogram,
                hubs: model.hubs,
                correctionEnabled: model.correctionEnabled,
                errorMessage: model.proofError,
                onCorrectionChanged: { enabled in
                    Task { await model.setCorrection(enabled) }
                },
                onPlay: { track in
                    model.focus(track)
                    playback.toggle(track)
                }
            )
            if let rec = model.selected {
                MathPanel(seed: map.seed, rec: rec, axis: map.axis)
            }
        }
    }

    /// The spectrogram follows whatever is playing, else the selection, else
    /// the seed.
    private func spotlightTrack(_ map: VizMap) -> Track {
        if let playing = playback.nowPlaying { return playing }
        return model.selected?.track ?? map.seed.track
    }

    private func recPicker(_ map: VizMap) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(map.recs) { rec in
                    Button {
                        model.selectAndPlay(rec) { playback.toggle($0) }
                    } label: {
                        VStack(spacing: 4) {
                            Artwork(url: rec.artworkURL)
                                .frame(width: 52, height: 52)
                                .overlay {
                                    if rec.trackID == model.selected?.trackID {
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(Color.accentColor, lineWidth: 3)
                                    }
                                }
                            Text(rec.title)
                                .font(.caption2)
                                .lineLimit(1)
                                .frame(width: 60)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func galaxyCallout(_ point: GalaxySelection) -> some View {
        Button {
            model.focus(point)
            playback.toggle(point.track)
        } label: {
            HStack(spacing: 12) {
                Artwork(url: point.track.artworkURL)
                    .frame(width: 54, height: 54)
                VStack(alignment: .leading, spacing: 2) {
                    Text(point.track.title)
                        .font(.headline)
                        .lineLimit(1)
                    Text(point.track.artist)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Image(systemName: playback.nowPlayingID == point.id && playback.isPlaying
                      ? "pause.fill" : "play.fill")
                    .font(.title3)
                    .foregroundStyle(Color.accentColor)
            }
            .padding(10)
            .background(.thinMaterial, in: .rect(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Play \(point.track.title) by \(point.track.artist)")
    }
}

/// The actual numbers behind the selected recommendation's score.
private struct MathPanel: View {
    let seed: VizMap.SeedPoint
    let rec: VizMap.Rec
    let axis: VizMap.AxisInfo

    // Analysis stores groove already normalized to [0, 1] (tempo on a log
    // scale), so the bars plot the values directly.
    private static let grooveLabels = ["Tempo", "Beat conf.", "Onsets", "Dance"]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Why \u{201C}\(rec.title)\u{201D} scored \(rec.score, specifier: "%.3f")")
                .font(.headline)

            scoreFormula
                .font(.system(.footnote, design: .monospaced))
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.quaternary.opacity(0.5), in: .rect(cornerRadius: 8))

            if let seedGroove = seed.groove, let recGroove = rec.groove,
               seedGroove.count == 4, recGroove.count == 4 {
                grooveComparison(seed: seedGroove, rec: recGroove)
            }
        }
        .padding()
        .background(.background.secondary, in: .rect(cornerRadius: 12))
    }

    @ViewBuilder private var scoreFormula: some View {
        let m = rec.math
        VStack(alignment: .leading, spacing: 4) {
            if m.metric == "cosine" {
                Text("cos \u{03B8} = a\u{00B7}b / (\u{2016}a\u{2016}\u{2016}b\u{2016})")
                Text("      = \(m.dot, specifier: "%.2f") / (\(m.seedNorm, specifier: "%.2f") \u{00D7} \(m.recNorm, specifier: "%.2f"))")
                Text("      = \(m.dot / (m.seedNorm * m.recNorm), specifier: "%.3f")")
            } else if let d = m.distance {
                Text("score = 1 / (1 + \u{2016}a \u{2212} b\u{2016})")
                Text("      = 1 / (1 + \(d, specifier: "%.2f"))")
                Text("      = \(1 / (1 + d), specifier: "%.3f")")
            }
            if axis.direction == -1, let c = m.centrality {
                Text("ranked by distance, minus \(c, specifier: "%.3f") centrality")
                Text("(so \u{201C}weird for everything\u{201D} can\u{2019}t win every seed)")
            }
        }
    }

    private func grooveComparison(seed: [Double], rec: [Double]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Groove: seed vs. this track")
                .font(.subheadline.weight(.medium))
            HStack(alignment: .bottom, spacing: 18) {
                ForEach(0..<4, id: \.self) { i in
                    VStack(spacing: 4) {
                        HStack(alignment: .bottom, spacing: 4) {
                            bar(seed[i], color: .yellow)
                            bar(rec[i], color: .accentColor)
                        }
                        Text(Self.grooveLabels[i])
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.2f / %.2f", seed[i], rec[i]))
                            .font(.system(.caption2, design: .monospaced))
                    }
                }
            }
        }
    }

    private func bar(_ fraction: Double, color: Color) -> some View {
        RoundedRectangle(cornerRadius: 2)
            .fill(color)
            .frame(width: 14, height: max(4, min(fraction, 1) * 56))
    }
}
