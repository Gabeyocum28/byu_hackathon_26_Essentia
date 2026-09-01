//
//  InsightsView.swift
//  Hackathon
//
//  The wow screen: where the corpus lies (galaxy map of embedding space), what
//  the playing track looks like (mel-spectrogram), and the actual arithmetic
//  behind the selected recommendation's score.
//

import SwiftUI

@MainActor
@Observable
final class InsightsModel {
    let seed: Track
    let axis: Axis
    var map: VizMap?
    var selected: VizMap.Rec?
    var isLoading = true
    var errorMessage: String?

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
        } catch {
            errorMessage = "The math needs an analyzed corpus — is the server up?"
        }
        isLoading = false
    }

    /// One intent keeps the visual selection and audible selection together.
    func selectAndPlay(_ rec: VizMap.Rec, play: (Track) -> Void) {
        selected = rec
        play(rec.track)
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
                VStack(alignment: .leading, spacing: 6) {
                    Text("\(map.points.ids.count) tracks in 1280-dimensional "
                         + "sound space, flattened to 2D (PCA)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    GalaxyMapView(map: map, selected: $model.selected)
                        .aspectRatio(1, contentMode: .fit)
                        .background(.black, in: .rect(cornerRadius: 12))
                }

                recPicker(map)

                SpectrogramView(track: spotlightTrack(map))

                if let rec = model.selected {
                    MathPanel(seed: map.seed, rec: rec, axis: map.axis)
                }
            }
            .padding()
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
