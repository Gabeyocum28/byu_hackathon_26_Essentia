//
//  GalaxyMapView.swift
//  Hackathon
//
//  Interactive PCA starfield. Pinch and drag alter one screen-space
//  PointTransform, which is also used for drawing, culling, and hit testing.
//

import SwiftUI

struct GalaxySelection: Identifiable {
    let track: Track
    let x: Double
    let y: Double

    var id: String { track.trackID }
}

struct GalaxyMapView: View {
    let map: VizMap
    let selectedTrackID: String?
    let walk: VizWalk?
    let walkProgress: CGFloat
    let onSelect: (GalaxySelection) -> Void

    @State private var zoom: CGFloat = 1
    @State private var pan: CGSize = .zero
    @GestureState private var gestureZoom: CGFloat = 1
    @GestureState private var gesturePan: CGSize = .zero

    private var activeZoom: CGFloat {
        min(max(zoom * gestureZoom, 1), 8)
    }

    private var activePan: CGSize {
        CGSize(width: pan.width + gesturePan.width,
               height: pan.height + gesturePan.height)
    }

    var body: some View {
        GeometryReader { proxy in
            let transform = PointTransform(
                x: map.points.x, y: map.points.y, size: proxy.size,
                zoom: activeZoom, pan: activePan
            )

            Canvas { context, size in
                draw(in: context, size: size, with: transform)
            }
            .contentShape(Rectangle())
            .simultaneousGesture(
                SpatialTapGesture().onEnded { value in
                    select(nearest: value.location, transform: transform)
                }
            )
            .simultaneousGesture(
                DragGesture(minimumDistance: 6)
                    .updating($gesturePan) { value, state, _ in
                        state = value.translation
                    }
                    .onEnded { value in
                        pan = CGSize(width: pan.width + value.translation.width,
                                     height: pan.height + value.translation.height)
                    }
            )
            .simultaneousGesture(
                MagnifyGesture()
                    .updating($gestureZoom) { value, state, _ in
                        state = value.magnification
                    }
                    .onEnded { value in
                        zoom = min(max(zoom * value.magnification, 1), 8)
                    }
            )
            .accessibilityLabel("Music embedding galaxy")
            .accessibilityHint("Pinch to zoom, drag to pan, or tap a star")
        }
    }

    private func draw(in context: GraphicsContext, size: CGSize,
                      with transform: PointTransform) {
        // At high zoom most points are outside the viewport; never ask Canvas
        // to rasterize them. The same transformed coordinate drives hit tests.
        for i in map.points.ids.indices {
            let p = transform.place(x: map.points.x[i], y: map.points.y[i])
            guard transform.isVisible(p, in: size, margin: 10) else { continue }
            if map.points.ids[i] == selectedTrackID {
                context.fill(dot(at: p, radius: 7),
                             with: .color(.white.opacity(0.22)))
            }
            context.fill(dot(at: p, radius: 1.5),
                         with: .color(.white.opacity(0.55)))
        }

        let seedPoint = transform.place(x: map.seed.x, y: map.seed.y)

        for rec in map.recs {
            let p = transform.place(x: rec.x, y: rec.y)
            guard transform.isVisible(p, in: size, margin: 20) else { continue }
            var line = Path()
            line.move(to: seedPoint)
            line.addLine(to: p)
            context.stroke(line, with: .color(.accentColor.opacity(0.35)),
                           lineWidth: 1)
        }
        for rec in map.recs {
            let p = transform.place(x: rec.x, y: rec.y)
            guard transform.isVisible(p, in: size, margin: 12) else { continue }
            if rec.trackID == selectedTrackID {
                context.fill(dot(at: p, radius: 11),
                             with: .color(.accentColor.opacity(0.25)))
                context.fill(dot(at: p, radius: 7), with: .color(.accentColor))
            } else {
                context.fill(dot(at: p, radius: 4.5), with: .color(.accentColor))
            }
        }

        drawWalk(in: context, walk: walk, progress: walkProgress,
                 transform: transform)

        if transform.isVisible(seedPoint, in: size, margin: 16) {
            for (radius, opacity) in [(CGFloat(14), 0.15), (9, 0.35), (5.5, 1.0)] {
                context.fill(dot(at: seedPoint, radius: radius),
                             with: .color(.yellow.opacity(opacity)))
            }
        }
    }

    private func drawWalk(in context: GraphicsContext, walk: VizWalk?,
                          progress: CGFloat, transform: PointTransform) {
        guard let walk, walk.path.count >= 2,
              let first = walk.path.first, let last = walk.path.last else { return }

        let start = transform.place(x: first.x, y: first.y)
        let end = transform.place(x: last.x, y: last.y)
        var chord = Path()
        chord.move(to: start)
        chord.addLine(to: end)
        context.stroke(
            chord, with: .color(.white.opacity(0.35)),
            style: StrokeStyle(lineWidth: 1, dash: [5, 4])
        )

        let segmentProgress = min(max(progress, 0), 1) * CGFloat(walk.path.count - 1)
        for index in 0..<(walk.path.count - 1) {
            let amount = min(max(segmentProgress - CGFloat(index), 0), 1)
            guard amount > 0 else { continue }
            let a = transform.place(x: walk.path[index].x, y: walk.path[index].y)
            let b = transform.place(x: walk.path[index + 1].x,
                                    y: walk.path[index + 1].y)
            let partial = CGPoint(x: a.x + (b.x - a.x) * amount,
                                  y: a.y + (b.y - a.y) * amount)
            var edge = Path()
            edge.move(to: a)
            edge.addLine(to: partial)
            context.stroke(edge, with: .color(.yellow), lineWidth: 2.5)
            context.fill(dot(at: a, radius: 4), with: .color(.yellow))
            if amount == 1 {
                context.fill(dot(at: b, radius: 4), with: .color(.yellow))
            }
        }
    }

    private func dot(at p: CGPoint, radius: CGFloat) -> Path {
        Path(ellipseIn: CGRect(x: p.x - radius, y: p.y - radius,
                               width: 2 * radius, height: 2 * radius))
    }

    private func select(nearest location: CGPoint, transform: PointTransform) {
        guard let index = transform.nearestIndex(
            to: location, x: map.points.x, y: map.points.y,
            maximumDistance: 36
        ), map.points.tracks.indices.contains(index) else { return }
        onSelect(GalaxySelection(track: map.points.tracks[index],
                                 x: map.points.x[index], y: map.points.y[index]))
    }
}

/// Maps PCA coordinates into screen points with padding, then applies the
/// user's viewport around the view center. Internal so the math can be tested.
struct PointTransform {
    private let scale: CGFloat
    private let dataCenter: CGPoint
    private let viewCenter: CGPoint
    private let zoom: CGFloat
    private let pan: CGSize

    init(x: [Double], y: [Double], size: CGSize,
         zoom: CGFloat = 1, pan: CGSize = .zero) {
        let minX = x.min() ?? 0, maxX = x.max() ?? 1
        let minY = y.min() ?? 0, maxY = y.max() ?? 1
        let span = max(maxX - minX, maxY - minY, 1e-9)
        let padding: CGFloat = 16
        let fit = min(size.width, size.height) - 2 * padding
        scale = fit > 0 ? fit / span : 1
        dataCenter = CGPoint(x: (minX + maxX) / 2, y: (minY + maxY) / 2)
        viewCenter = CGPoint(x: size.width / 2, y: size.height / 2)
        self.zoom = min(max(zoom, 1), 8)
        self.pan = pan
    }

    /// Fixed-radius, origin-centered variant for data known to be zero-mean
    /// under any linear map (e.g. PCA scores viewed through an arbitrary
    /// orthonormal 2-frame): `scale` and `dataCenter` never depend on the
    /// current projection, so a rotating view doesn't rescale/"breathe"
    /// frame to frame. `radius` should bound the largest possible projected
    /// magnitude — e.g. the max L2 norm of the un-projected vectors, since
    /// projection through an orthonormal frame can never exceed it.
    init(radius: Double, size: CGSize, zoom: CGFloat = 1, pan: CGSize = .zero) {
        let span = max(radius * 2, 1e-9)
        let padding: CGFloat = 16
        let fit = min(size.width, size.height) - 2 * padding
        scale = fit > 0 ? fit / span : 1
        dataCenter = .zero
        viewCenter = CGPoint(x: size.width / 2, y: size.height / 2)
        self.zoom = min(max(zoom, 1), 8)
        self.pan = pan
    }

    /// Explicit-bounds variant: same scale/center math as the x/y-array
    /// initializer, but from precomputed bounds instead of scanning the
    /// arrays — for callers that cache a data set's extent once and redraw
    /// it many times (e.g. a slider-driven overlay) without re-scanning.
    init(minX: Double, maxX: Double, minY: Double, maxY: Double, size: CGSize,
         zoom: CGFloat = 1, pan: CGSize = .zero) {
        let span = max(maxX - minX, maxY - minY, 1e-9)
        let padding: CGFloat = 16
        let fit = min(size.width, size.height) - 2 * padding
        scale = fit > 0 ? fit / span : 1
        dataCenter = CGPoint(x: (minX + maxX) / 2, y: (minY + maxY) / 2)
        viewCenter = CGPoint(x: size.width / 2, y: size.height / 2)
        self.zoom = min(max(zoom, 1), 8)
        self.pan = pan
    }

    func place(x: Double, y: Double) -> CGPoint {
        let baseX = viewCenter.x + (x - dataCenter.x) * scale
        let baseY = viewCenter.y - (y - dataCenter.y) * scale
        return CGPoint(
            x: viewCenter.x + (baseX - viewCenter.x) * zoom + pan.width,
            y: viewCenter.y + (baseY - viewCenter.y) * zoom + pan.height
        )
    }

    func nearestIndex(to location: CGPoint, x: [Double], y: [Double],
                      maximumDistance: CGFloat) -> Int? {
        let count = min(x.count, y.count)
        var bestIndex: Int?
        var bestDistance = maximumDistance * maximumDistance
        for index in 0..<count {
            let point = place(x: x[index], y: y[index])
            let dx = point.x - location.x
            let dy = point.y - location.y
            let distance = dx * dx + dy * dy
            if distance <= bestDistance {
                bestDistance = distance
                bestIndex = index
            }
        }
        return bestIndex
    }

    func isVisible(_ point: CGPoint, in size: CGSize, margin: CGFloat) -> Bool {
        CGRect(origin: .zero, size: size)
            .insetBy(dx: -margin, dy: -margin)
            .contains(point)
    }
}
