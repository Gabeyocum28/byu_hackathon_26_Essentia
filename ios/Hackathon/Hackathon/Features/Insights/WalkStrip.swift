import SwiftUI

struct WalkStrip: View {
    let walk: VizWalk
    let onPlay: (VizWalk.Step) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("k-NN geodesic", systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text("\(walk.detour, specifier: "%.2f")× detour")
                    .font(.system(.caption, design: .monospaced).weight(.bold))
                    .foregroundStyle(.yellow)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(.yellow.opacity(0.14), in: .capsule)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(walk.path.enumerated()), id: \.element.id) { index, step in
                        Button { onPlay(step) } label: {
                            VStack(spacing: 4) {
                                Artwork(url: step.artworkURL)
                                    .frame(width: 52, height: 52)
                                Text("\(index + 1)")
                                    .font(.system(.caption2, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                Text(step.title)
                                    .font(.caption2)
                                    .lineLimit(1)
                                    .frame(width: 58)
                            }
                        }
                        .buttonStyle(.plain)
                        if index < walk.path.count - 1 {
                            Image(systemName: "chevron.right")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            Text("geodesic \(walk.geodesic, specifier: "%.2f") · ambient chord \(walk.ambient, specifier: "%.2f")")
                .font(.system(.caption2, design: .monospaced))
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .background(.quaternary.opacity(0.45), in: .rect(cornerRadius: 12))
    }
}
