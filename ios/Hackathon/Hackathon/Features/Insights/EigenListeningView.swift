//
//  EigenListeningView.swift
//  Hackathon
//
//  T2.4 eigen-listening rails: "what does PC1 sound like?" One rail per
//  principal component (1-4), low-extreme tracks on the left, high-extreme
//  on the right, both playable through the shared playback environment.
//

import SwiftUI

struct EigenListeningView: View {
    let model: InsightsModel
    let onPlay: (Track) -> Void

    private let pcs = [1, 2, 3, 4]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Eigen-listening")
                .font(.headline)
            Text("What each principal component sounds like \u{2014} low extreme vs. high extreme")
                .font(.caption)
                .foregroundStyle(.secondary)

            ForEach(pcs, id: \.self) { pc in
                rail(pc)
                    .task(id: pc) { await model.loadExtremesIfNeeded(pc: pc) }
            }
        }
        .padding()
        .background(.background.secondary, in: .rect(cornerRadius: 12))
    }

    @ViewBuilder
    private func rail(_ pc: Int) -> some View {
        if let extremes = model.extremesByPC[pc] {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("PC\(pc)").font(.subheadline.weight(.semibold))
                    Spacer()
                    Text("\(extremes.variancePct, specifier: "%.1f")% variance")
                        .font(.system(.caption2, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                // Two stacked rows, not one wide one: eight 42pt artworks
                // side by side need ~500pt and ran off every iPhone.
                end(label: "low", tracks: extremes.low)
                end(label: "high", tracks: extremes.high)
            }
            .padding(10)
            .background(.quaternary.opacity(0.35), in: .rect(cornerRadius: 10))
        } else if model.extremesErrors[pc] != nil {
            HStack {
                Text("PC\(pc)").font(.subheadline.weight(.semibold))
                Spacer()
                Text("rail unavailable").font(.caption).foregroundStyle(.secondary)
            }
        } else {
            HStack {
                Text("PC\(pc)").font(.subheadline.weight(.semibold))
                Spacer()
                ProgressView()
            }
        }
    }

    /// One end of a component: a label and its tracks, scrollable so a
    /// long rail never pushes the card wider than the screen.
    private func end(label: String, tracks: [VizExtremesResponse.ExtremeTrack]) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
                .frame(width: 30, alignment: .leading)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(tracks) { extreme in
                        Button { onPlay(extreme.track) } label: {
                            Artwork(url: extreme.track.artworkURL)
                                .frame(width: 42, height: 42)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Play \(extreme.title) by \(extreme.artist)")
                    }
                }
                .padding(.vertical, 1)
            }
        }
    }
}
