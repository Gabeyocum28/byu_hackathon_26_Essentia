import SwiftUI

struct ProofModeView: View {
    let map: VizMap
    let histogram: VizHistogram?
    let hubs: VizHubs?
    let correctionEnabled: Bool
    let errorMessage: String?
    let onCorrectionChanged: (Bool) -> Void
    let onPlay: (Track) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if let histogram {
                VStack(alignment: .leading, spacing: 8) {
                    Text("How special is this neighborhood?")
                        .font(.headline)
                    HistogramPlot(histogram: histogram)
                        .frame(height: 180)
                    Text("Top recommendations are closer than \(histogram.percentile, specifier: "%.1f")% of the corpus")
                        .font(.subheadline.weight(.semibold))
                    Text("random σ = \(histogram.null.sd, specifier: "%.4f") · corpus μ = \(histogram.corpus.mean, specifier: "%.3f")")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            } else {
                ProgressView("Measuring the corpus …")
            }

            VStack(alignment: .leading, spacing: 8) {
                Toggle("Surprise correction", isOn: Binding(
                    get: { correctionEnabled },
                    set: onCorrectionChanged
                ))
                .font(.headline)
                Text(correctionEnabled
                     ? "subtracting each track’s mean corpus similarity"
                     : "raw distance — hubs can dominate")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let errorMessage {
                    Text(errorMessage).font(.caption).foregroundStyle(.red)
                }
            }
            .padding(12)
            .background(.quaternary.opacity(0.45), in: .rect(cornerRadius: 12))

            if let hubs {
                HubHallView(hubs: hubs, onPlay: onPlay)
            }
        }
    }
}

private struct HistogramPlot: View {
    let histogram: VizHistogram

    var body: some View {
        Canvas { context, size in
            guard !histogram.counts.isEmpty else { return }
            let total = Double(histogram.counts.reduce(0, +))
            let binWidth = 2.0 / Double(histogram.counts.count)
            let nullPeak = total * binWidth /
                (histogram.null.sd * sqrt(2 * Double.pi))
            let maximum = max(Double(histogram.counts.max() ?? 1), nullPeak, 1)
            let width = size.width / CGFloat(histogram.counts.count)

            for (index, count) in histogram.counts.enumerated() {
                let height = size.height * 0.86 * CGFloat(Double(count) / maximum)
                let rect = CGRect(x: CGFloat(index) * width,
                                  y: size.height - height,
                                  width: max(width - 1, 1), height: height)
                context.fill(Path(rect), with: .color(.cyan.opacity(0.72)))
            }

            var nullPath = Path()
            for pixel in 0...Int(size.width) {
                let x = -1.0 + 2.0 * Double(pixel) / max(Double(size.width), 1)
                let z = (x - histogram.null.mean) / histogram.null.sd
                let density = exp(-0.5 * z * z) /
                    (histogram.null.sd * sqrt(2 * Double.pi))
                let expected = total * binWidth * density
                let point = CGPoint(
                    x: CGFloat(pixel),
                    y: size.height - size.height * 0.86 * CGFloat(expected / maximum)
                )
                if pixel == 0 { nullPath.move(to: point) } else { nullPath.addLine(to: point) }
            }
            context.stroke(nullPath, with: .color(.white.opacity(0.9)), lineWidth: 1.5)

            for score in histogram.recScores {
                let x = CGFloat(min(max((score + 1) / 2, 0), 1)) * size.width
                var marker = Path()
                marker.move(to: CGPoint(x: x, y: 0))
                marker.addLine(to: CGPoint(x: x, y: size.height))
                context.stroke(marker, with: .color(.yellow.opacity(0.75)), lineWidth: 1)
            }
        }
        .padding(8)
        .background(.black, in: .rect(cornerRadius: 10))
        .accessibilityLabel("Similarity histogram with random-noise overlay")
    }
}

private struct HubHallView: View {
    let hubs: VizHubs
    let onPlay: (Track) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Hub hall of fame").font(.headline)
            hubRow("Most frequent neighbors", entries: hubs.hubs.map {
                ($0.track, "\($0.count) lists")
            })
            hubRow("Most central", entries: hubs.central.map {
                ($0.track, String(format: "μ %.3f", $0.centrality))
            })
            hubRow("Most isolated", entries: hubs.isolated.map {
                ($0.track, String(format: "μ %.3f", $0.centrality))
            })
        }
    }

    private func hubRow(_ title: String, entries: [(Track, String)]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(entries, id: \.0.id) { track, value in
                        Button { onPlay(track) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Artwork(url: track.artworkURL).frame(width: 64, height: 64)
                                Text(track.title).font(.caption2).lineLimit(1).frame(width: 68, alignment: .leading)
                                Text(value)
                                    .font(.system(.caption2, design: .monospaced))
                                    .foregroundStyle(.yellow)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}
