//
//  WhySimilarView.swift
//  Hackathon
//
//  T2.6 — the answer to the question every skeptic actually asks: WHY are
//  these two songs similar? One bar per frequency band, each showing how far
//  the pair's cosine falls when that band is deleted from the seed and the
//  counterfactual is pushed back through the real model. Tap a bar to hear
//  the band that carries the similarity.
//
//  The drops are deliberately not normalized to sum to the score: bands
//  interact inside the network, so single-band occlusion is a first-order
//  surrogate for Shapley values, not an additive decomposition.
//

import SwiftUI

struct WhySimilarView: View {
    let recTitle: String
    let attribution: VizAttribution?
    let isWorkerSilent: Bool
    let onSolo: (VizAttribution.Band) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Why similar? — \u{201C}\(recTitle)\u{201D}")
                .font(.headline)

            if let attribution, attribution.isReady,
               let bands = attribution.bands, !bands.isEmpty {
                ready(bands: bands, base: attribution.base)
            } else if let attribution, attribution.status == "failed" {
                message("The worker couldn\u{2019}t explain this pair"
                        + (attribution.error.map { " — \($0)" } ?? "."))
            } else if isWorkerSilent {
                message("Still waiting on the analysis worker. Band-solo on the "
                        + "spectrogram works without it.")
            } else {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Deleting each band and re-running the model \u{2026}")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding()
        .background(.background.secondary, in: .rect(cornerRadius: 12))
    }

    private func message(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
    }

    private func ready(bands: [VizAttribution.Band], base: Double?) -> some View {
        let peak = max(bands.map(\.delta).max() ?? 0, 0.0001)
        return VStack(alignment: .leading, spacing: 8) {
            if let base {
                Text("cos = \(base, specifier: "%.3f") \u{2014} tap a band to hear it")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            HStack(alignment: .bottom, spacing: 3) {
                ForEach(bands) { band in
                    Button { onSolo(band) } label: {
                        bar(band, peak: peak)
                    }
                    .buttonStyle(.plain)
                    // Ten bands share whatever width there is, so the row
                    // fits every screen instead of running off the card.
                    .frame(maxWidth: .infinity)
                    .accessibilityLabel(
                        "\(Int(band.loHz)) to \(Int(band.hiHz)) hertz, "
                        + "similarity drops \(String(format: "%.3f", band.delta))"
                    )
                }
            }
            .frame(height: 116)

            Text("Bar = how much the model\u{2019}s similarity drops when that band "
                 + "is deleted. They don\u{2019}t sum to the score \u{2014} bands interact.")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }

    private func bar(_ band: VizAttribution.Band, peak: Double) -> some View {
        // Negative drops happen (removing a band can nudge the pair closer);
        // they carry no explanatory weight, so they render as a stub.
        let fraction = max(band.delta, 0) / peak
        let isTallest = band.delta >= peak - 1e-9
        return VStack(spacing: 3) {
            Spacer(minLength: 0)
            Text(String(format: "%.2f", band.delta))
                .font(.system(size: 8, design: .monospaced))
                .foregroundStyle(.secondary)
            RoundedRectangle(cornerRadius: 3)
                .fill(isTallest ? Color.accentColor : Color.accentColor.opacity(0.45))
                .frame(height: max(3, CGFloat(fraction) * 74))
            Text(Self.label(band.loHz))
                .font(.system(size: 8))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }

    /// Compact axis label: 240, 1.2k, 7.8k.
    static func label(_ hz: Double) -> String {
        hz >= 1000
            ? String(format: "%.1fk", hz / 1000)
            : String(Int(hz.rounded()))
    }
}
