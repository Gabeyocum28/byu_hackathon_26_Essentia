//
//  TopologyView.swift
//  Hackathon
//
//  T2.2 Topology / H0 persistence: single-linkage clustering IS the minimum
//  spanning tree, and its edge weights ARE the H0 barcode's death times. A
//  threshold slider draws MST edges below it and recolors components live;
//  a barcode strip beneath shows every merge as a bar from 0 to its death.
//

import SwiftUI

/// Union-find over point indices. Pure and independently testable: the view
/// only ever asks "what are the components at threshold d".
struct UnionFind {
    private var parent: [Int]
    private var rank: [Int]

    init(count: Int) {
        parent = Array(0..<count)
        rank = Array(repeating: 0, count: count)
    }

    mutating func find(_ x: Int) -> Int {
        if parent[x] != x {
            parent[x] = find(parent[x])
        }
        return parent[x]
    }

    mutating func union(_ a: Int, _ b: Int) {
        let ra = find(a), rb = find(b)
        guard ra != rb else { return }
        if rank[ra] < rank[rb] {
            parent[ra] = rb
        } else if rank[ra] > rank[rb] {
            parent[rb] = ra
        } else {
            parent[rb] = ra
            rank[ra] += 1
        }
    }
}

/// Single-linkage components of the MST at a given distance threshold: union
/// every edge with d <= threshold, then read off each point's root.
enum TopologyComponents {
    static func components(count: Int, edges: [(i: Int, j: Int, d: Double)],
                           threshold: Double) -> [Int] {
        var uf = UnionFind(count: count)
        for edge in edges where edge.d <= threshold {
            uf.union(edge.i, edge.j)
        }
        var roots = [Int](repeating: 0, count: count)
        for i in 0..<count { roots[i] = uf.find(i) }
        return roots
    }
}

struct TopologyView: View {
    let tour: VizTour?
    let mst: VizMST?
    let tourError: String?
    let mstError: String?

    @State private var threshold: Double = 0
    @State private var thresholdInitialized = false

    var body: some View {
        Group {
            if let tourError {
                message(tourError)
            } else if let mstError {
                message(mstError)
            } else if let tour, let mst {
                content(tour: tour, mst: mst)
            } else {
                ProgressView("Building the topology \u{2026}")
                    .tint(.white)
                    .frame(maxWidth: .infinity, minHeight: 220)
            }
        }
    }

    private func message(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, minHeight: 220)
    }

    private func content(tour: VizTour, mst: VizMST) -> some View {
        let positions = Self.positions(tour: tour, mstIDs: mst.ids)
        let maxDistance = max(mst.edges.map(\.d).max() ?? 0, 0.0001)

        return VStack(alignment: .leading, spacing: 10) {
            Canvas { ctx, size in
                draw(positions: positions, edges: mst.edges, threshold: threshold,
                     in: ctx, size: size)
            }
            .aspectRatio(1, contentMode: .fit)
            .background(.black, in: .rect(cornerRadius: 12))
            .accessibilityLabel("Topology map: single-linkage components below the merge threshold")

            VStack(alignment: .leading, spacing: 4) {
                Text("Merge threshold: \(threshold, specifier: "%.3f") cosine distance")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $threshold, in: 0...maxDistance)
            }

            barcode(edges: mst.edges, maxDistance: maxDistance)
        }
        .task(id: mst.ids.count) {
            guard !thresholdInitialized else { return }
            thresholdInitialized = true
            threshold = 0
        }
    }

    /// Static 2-d layout for the starfield: PC1/PC2 from the tour payload,
    /// looked up by id and reordered to match the MST's own id order (the
    /// two endpoints are not guaranteed to return ids in the same order).
    private static func positions(tour: VizTour, mstIDs: [String]) -> [(x: Double, y: Double)] {
        var lookup: [String: (Double, Double)] = [:]
        lookup.reserveCapacity(tour.ids.count)
        for (index, id) in tour.ids.enumerated() {
            let row = tour.coords[index]
            lookup[id] = (Double(row[0]), Double(row[1]))
        }
        return mstIDs.map { lookup[$0] ?? (0, 0) }
    }

    /// Recomputed on every draw call (union-find over <= a few thousand
    /// edges is O(n alpha)); no separate throttling for slider drags — it
    /// stayed smooth in manual testing at this corpus size.
    private func draw(positions: [(x: Double, y: Double)], edges: [VizMST.Edge],
                      threshold: Double, in context: GraphicsContext, size: CGSize) {
        guard !positions.isEmpty else { return }
        let xs = positions.map(\.x)
        let ys = positions.map(\.y)
        let transform = PointTransform(x: xs, y: ys, size: size)

        let components = TopologyComponents.components(
            count: positions.count,
            edges: edges.map { (i: $0.i, j: $0.j, d: $0.d) },
            threshold: threshold
        )
        var sizes: [Int: Int] = [:]
        for component in components { sizes[component, default: 0] += 1 }
        let ranked = sizes.filter { $0.value > 1 }
            .sorted { $0.value > $1.value }
            .map(\.key)

        func color(for component: Int) -> Color {
            guard let size = sizes[component], size > 1,
                  let rank = ranked.firstIndex(of: component) else {
                return .white.opacity(0.25)
            }
            let hue = Double(rank % 12) / 12.0
            return Color(hue: hue, saturation: 0.72, brightness: 0.98)
        }

        for edge in edges where edge.d <= threshold {
            guard positions.indices.contains(edge.i), positions.indices.contains(edge.j) else { continue }
            let a = transform.place(x: positions[edge.i].x, y: positions[edge.i].y)
            let b = transform.place(x: positions[edge.j].x, y: positions[edge.j].y)
            guard transform.isVisible(a, in: size, margin: 20) || transform.isVisible(b, in: size, margin: 20)
            else { continue }
            var path = Path()
            path.move(to: a)
            path.addLine(to: b)
            context.stroke(path, with: .color(.white.opacity(0.14)), lineWidth: 0.6)
        }

        for index in positions.indices {
            let p = transform.place(x: positions[index].x, y: positions[index].y)
            guard transform.isVisible(p, in: size, margin: 6) else { continue }
            context.fill(
                Path(ellipseIn: CGRect(x: p.x - 1.4, y: p.y - 1.4, width: 2.8, height: 2.8)),
                with: .color(color(for: components[index]))
            )
        }
    }

    /// H0 persistence diagram: one bar per merge, sorted-ascending edge
    /// weights as bar lengths, with a cursor at the current threshold.
    private func barcode(edges: [VizMST.Edge], maxDistance: Double) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("H0 persistence \u{2014} one bar per merge, length = death (edge weight)")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Canvas { ctx, size in
                guard !edges.isEmpty else { return }
                let barHeight = max(1, size.height / CGFloat(edges.count) - 1)
                for (index, edge) in edges.enumerated() {
                    let y = CGFloat(index) * (barHeight + 1)
                    let width = max(CGFloat(edge.d / maxDistance) * size.width, 1)
                    ctx.fill(Path(CGRect(x: 0, y: y, width: width, height: barHeight)),
                             with: .color(.cyan.opacity(0.6)))
                }
                let cursorX = CGFloat(threshold / maxDistance) * size.width
                var cursor = Path()
                cursor.move(to: CGPoint(x: cursorX, y: 0))
                cursor.addLine(to: CGPoint(x: cursorX, y: size.height))
                ctx.stroke(cursor, with: .color(.yellow), lineWidth: 1.5)
            }
            .frame(height: 46)
            .background(.black, in: .rect(cornerRadius: 8))
            .accessibilityLabel("H0 persistence barcode with a cursor at the current threshold")
        }
    }
}
