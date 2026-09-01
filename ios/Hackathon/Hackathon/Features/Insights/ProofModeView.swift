//
//  ProofModeView.swift
//  Hackathon
//
//  "Is 0.83 actually good?" — the seed against the whole corpus, the same
//  chart under random noise for comparison, and the hubness correction that
//  stops a handful of tracks being everyone's answer.
//
//  Every section carries a "?" explanation: these are real statistics, and
//  the surprise-axis comparison in particular shows songs that deliberately
//  do NOT resemble the seed, which reads as a bug unless it is explained.
//

import SwiftUI

struct ProofModeView: View {
    let seedTitle: String
    let histogram: VizHistogram?
    let hubs: VizHubs?
    /// The surprise-axis picks, shown only inside the correction section.
    let surpriseRecs: [VizMap.Rec]
    let correctionEnabled: Bool
    let errorMessage: String?
    let onCorrectionChanged: (Bool) -> Void
    let onPlay: (Track) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            histogramSection
            correctionSection
            if let hubs { hubSection(hubs) }
        }
    }

    // MARK: - How special is this neighbourhood?

    private var histogramSection: some View {
        ExplainedSection(
            title: "How special is this match?",
            explanation: """
            Each bar counts how many tracks in the corpus sit at that \
            similarity to \u{201C}\(seedTitle)\u{201D}. Your recommendations are the \
            yellow marks out on the right tail.

            The white curve is the same chart if music were random noise: in \
            1280 dimensions two random directions are almost always nearly \
            perpendicular, with a spread of 1/\u{221A}1280 \u{2248} 0.028. Real music \
            sits far to the right of that curve — the gap is the structure \
            the model learned.
            """
        ) {
            if let histogram {
                VStack(alignment: .leading, spacing: 8) {
                    HistogramPlot(histogram: histogram)
                        .frame(height: 180)
                    Text("Top recommendations are closer than \(histogram.percentile, specifier: "%.1f")% of the corpus")
                        .font(.subheadline.weight(.semibold))
                    Text("random \u{03C3} = \(histogram.null.sd, specifier: "%.4f") \u{00B7} corpus \u{03BC} = \(histogram.corpus.mean, specifier: "%.3f")")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            } else {
                ProgressView("Measuring the corpus \u{2026}")
            }
        }
    }

    // MARK: - Hubness correction

    private var correctionSection: some View {
        ExplainedSection(
            title: "Surprise correction",
            explanation: """
            This section is a separate experiment on the \u{201C}surprise\u{201D} axis, \
            which hunts for tracks UNLIKE your seed — so the songs below are \
            not supposed to resemble it. That is what makes them a good test.

            In high dimensions a few tracks drift close to everything (hubs) \
            and would win every query. The correction subtracts each track's \
            average similarity to the whole corpus. Turn it off and watch the \
            same handful of hub tracks take over the list.
            """
        ) {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Correction \(correctionEnabled ? "on" : "off")", isOn: Binding(
                    get: { correctionEnabled },
                    set: onCorrectionChanged
                ))
                .font(.subheadline.weight(.medium))

                Text(correctionEnabled
                     ? "Subtracting each track\u{2019}s mean similarity to the corpus."
                     : "Raw distance — hub tracks can win every seed.")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                if !surpriseRecs.isEmpty {
                    Text("Surprise picks \u{2014} unlike your seed on purpose")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.secondary)
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(surpriseRecs) { rec in
                                Button { onPlay(rec.track) } label: {
                                    VStack(spacing: 4) {
                                        Artwork(url: rec.artworkURL)
                                            .frame(width: 52, height: 52)
                                        Text(rec.title)
                                            .font(.caption2)
                                            .lineLimit(1)
                                            .frame(width: 56)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.vertical, 2)
                    }
                }

                if let errorMessage {
                    Text(errorMessage).font(.caption).foregroundStyle(.red)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.45), in: .rect(cornerRadius: 12))
        }
    }

    // MARK: - Hub hall of fame

    private func hubSection(_ hubs: VizHubs) -> some View {
        ExplainedSection(
            title: "Hub hall of fame",
            explanation: """
            \u{201C}Most frequent neighbours\u{201D} counts how many other tracks list \
            each one among their 8 nearest. If the corpus were evenly spread \
            every track would appear about 8 times; the top hub appears in \
            far more, which is the curse of dimensionality showing up as a \
            recommendation bug.

            Most central and most isolated are the tracks with the highest \
            and lowest average similarity to everything else.
            """
        ) {
            VStack(alignment: .leading, spacing: 14) {
                hubRow("Most frequent neighbours",
                       entries: hubs.hubs.map { ($0.track, "\($0.count) lists") })
                hubRow("Most central",
                       entries: hubs.central.map { ($0.track, String(format: "\u{03BC} %.3f", $0.centrality)) })
                hubRow("Most isolated",
                       entries: hubs.isolated.map { ($0.track, String(format: "\u{03BC} %.3f", $0.centrality)) })
            }
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
                                Text(track.title)
                                    .font(.caption2).lineLimit(1)
                                    .frame(width: 68, alignment: .leading)
                                Text(value)
                                    .font(.system(.caption2, design: .monospaced))
                                    .foregroundStyle(.yellow)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 2)
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
