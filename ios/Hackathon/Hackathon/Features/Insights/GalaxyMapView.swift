//
//  GalaxyMapView.swift
//  Hackathon
//
//  The corpus as a starfield: every analyzed track is a dim dot placed by the
//  server's 2D PCA of embedding space, the seed glows, and the current
//  recommendations are lit and wired to the seed. Tap a lit dot to select it
//  for the math panel.
//

import SwiftUI

struct GalaxyMapView: View {
    let map: VizMap
    @Binding var selected: VizMap.Rec?

    var body: some View {
        GeometryReader { proxy in
            let transform = PointTransform(map: map, size: proxy.size)

            Canvas { context, _ in
                draw(in: context, with: transform)
            }
            .contentShape(Rectangle())
            .onTapGesture { location in
                select(nearest: location, transform: transform)
            }
        }
    }

    private func draw(in context: GraphicsContext, with transform: PointTransform) {
        // Corpus starfield.
        for i in map.points.ids.indices {
            let p = transform.place(x: map.points.x[i], y: map.points.y[i])
            context.fill(dot(at: p, radius: 1.5),
                         with: .color(.white.opacity(0.55)))
        }

        let seedPoint = transform.place(x: map.seed.x, y: map.seed.y)

        // Seed -> rec constellation lines, then the recs on top.
        for rec in map.recs {
            let p = transform.place(x: rec.x, y: rec.y)
            var line = Path()
            line.move(to: seedPoint)
            line.addLine(to: p)
            context.stroke(line, with: .color(.accentColor.opacity(0.35)),
                           lineWidth: 1)
        }
        for rec in map.recs {
            let p = transform.place(x: rec.x, y: rec.y)
            if rec.trackID == selected?.trackID {
                context.fill(dot(at: p, radius: 11),
                             with: .color(.accentColor.opacity(0.25)))
                context.fill(dot(at: p, radius: 7), with: .color(.accentColor))
            } else {
                context.fill(dot(at: p, radius: 4.5), with: .color(.accentColor))
            }
        }

        // The glowing seed.
        for (radius, opacity) in [(CGFloat(14), 0.15), (9, 0.35), (5.5, 1.0)] {
            context.fill(dot(at: seedPoint, radius: radius),
                         with: .color(.yellow.opacity(opacity)))
        }
    }

    private func dot(at p: CGPoint, radius: CGFloat) -> Path {
        Path(ellipseIn: CGRect(x: p.x - radius, y: p.y - radius,
                               width: 2 * radius, height: 2 * radius))
    }

    private func select(nearest location: CGPoint, transform: PointTransform) {
        func distanceSquared(_ rec: VizMap.Rec) -> CGFloat {
            let p = transform.place(x: rec.x, y: rec.y)
            return (p.x - location.x) * (p.x - location.x)
                 + (p.y - location.y) * (p.y - location.y)
        }
        guard let hit = map.recs.min(by: { distanceSquared($0) < distanceSquared($1) }),
              distanceSquared(hit) < 40 * 40 else { return }
        selected = hit
    }
}

/// Maps PCA coordinates into view points with padding, preserving aspect.
private struct PointTransform {
    let scale: CGFloat
    let offset: CGPoint
    let center: CGPoint

    init(map: VizMap, size: CGSize) {
        let xs = map.points.x + [map.seed.x]
        let ys = map.points.y + [map.seed.y]
        let minX = xs.min() ?? 0, maxX = xs.max() ?? 1
        let minY = ys.min() ?? 0, maxY = ys.max() ?? 1
        let span = max(maxX - minX, maxY - minY, 1e-9)
        let padding: CGFloat = 16
        let fit = min(size.width, size.height) - 2 * padding
        scale = fit > 0 ? fit / span : 1
        center = CGPoint(x: (minX + maxX) / 2, y: (minY + maxY) / 2)
        offset = CGPoint(x: size.width / 2, y: size.height / 2)
    }

    func place(x: Double, y: Double) -> CGPoint {
        CGPoint(x: offset.x + (x - center.x) * scale,
                y: offset.y - (y - center.y) * scale)
    }
}
