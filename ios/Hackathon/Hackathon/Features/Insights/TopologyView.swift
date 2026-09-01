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
/// every edge with d <= threshold, then read off each point's root. Rebuilds
/// from scratch every call — kept around as the reference implementation and
/// exercised directly in tests; the view itself uses the incremental variant
/// below so a slider drag doesn't redo this from scratch every frame.
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

/// Incrementally unions edges as the threshold rises, so dragging a slider
/// forward only unions the *newly* admitted edges instead of rebuilding
/// union-find from scratch every frame. `sortedEdges` must be ascending by
/// `d` (the MST contract guarantees this). Moving the threshold backward
/// past an already-applied merge is the one case that still rebuilds from
/// scratch — union-find has no "undo" — but that's the same O(n a(n)) cost
/// `TopologyComponents.components` always paid, not a regression.
struct IncrementalTopologyComponents {
    private(set) var appliedEdgeCount = 0
    private var unionFind: UnionFind
    private let sortedEdges: [(i: Int, j: Int, d: Double)]
    private let count: Int

    init(count: Int, sortedEdges: [(i: Int, j: Int, d: Double)]) {
        self.count = count
        self.sortedEdges = sortedEdges
        self.unionFind = UnionFind(count: count)
    }

    mutating func components(at threshold: Double) -> [Int] {
        let target = Self.edgeCount(upTo: threshold, in: sortedEdges)
        if target < appliedEdgeCount {
            unionFind = UnionFind(count: count)
            appliedEdgeCount = 0
        }
        while appliedEdgeCount < target {
            let edge = sortedEdges[appliedEdgeCount]
            unionFind.union(edge.i, edge.j)
            appliedEdgeCount += 1
        }
        var roots = [Int](repeating: 0, count: count)
        for i in 0..<count { roots[i] = unionFind.find(i) }
        return roots
    }

    /// Binary search over ascending-sorted edges: how many have d <= threshold.
    static func edgeCount(upTo threshold: Double,
                          in sortedEdges: [(i: Int, j: Int, d: Double)]) -> Int {
        var lo = 0, hi = sortedEdges.count
        while lo < hi {
            let mid = (lo + hi) / 2
            if sortedEdges[mid].d <= threshold { lo = mid + 1 } else { hi = mid }
        }
        return lo
    }
}

struct TopologyView: View {
    let tour: VizTour?
    let mst: VizMST?
    let tourError: String?
    let mstError: String?

    @State private var threshold: Double = 0
    @State private var thresholdInitialized = false
    @State private var layout: TopologyLayout?
    @State private var incremental: IncrementalTopologyComponents?

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
        VStack(alignment: .leading, spacing: 10) {
            Canvas { ctx, size in
                guard let layout else { return }
                draw(layout: layout, threshold: threshold, in: ctx, size: size)
            }
            .aspectRatio(1, contentMode: .fit)
            .background(.black, in: .rect(cornerRadius: 12))
            .accessibilityLabel("Topology map: single-linkage components below the merge threshold")

            if let layout, layout.missingIDCount > 0 {
                Text("\u{26A0}\u{FE0F} \(layout.missingIDCount) tracks have no position \u{2014} tour/MST snapshot mismatch, those edges are hidden")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Merge threshold: \(threshold, specifier: "%.3f") cosine distance")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $threshold, in: 0...(layout?.maxDistance ?? 0.0001))
            }

            barcode(layout: layout)
        }
        .task {
            // Built once from the (tour, mst) pair this view was handed and
            // never rebuilt on a threshold tick — the id lookup, filtering,
            // and bounds are all O(n) and slider drags happen far more often
            // than the data itself changes.
            guard layout == nil else { return }
            let built = Self.buildLayout(tour: tour, mst: mst)
            layout = built
            incremental = IncrementalTopologyComponents(
                count: built.positions.count, sortedEdges: built.edges
            )
            if !thresholdInitialized {
                thresholdInitialized = true
                threshold = 0
            }
        }
    }

    /// Cached, one-time-computed layout: positions (nil where an mst id has
    /// no match in the tour lookup), edges filtered to fully-resolved pairs
    /// (order preserved, so still ascending by d), and precomputed bounds so
    /// `draw` never re-scans the point set just to build a transform.
    /// `internal`, not `private`: exercised directly by
    /// `TopologyLayoutTests` for the missing-id guard (finding 4), so a
    /// mismatched tour/mst snapshot never regresses to the silent (0, 0)
    /// fallback without a test noticing.
    struct TopologyLayout {
        let positions: [(x: Double, y: Double)?]
        let edges: [(i: Int, j: Int, d: Double)]
        let maxDistance: Double
        let missingIDCount: Int
        let minX: Double
        let maxX: Double
        let minY: Double
        let maxY: Double
    }

    /// Static 2-d layout for the starfield: PC1/PC2 from the tour payload,
    /// looked up by id and reordered to match the MST's own id order (the
    /// two endpoints are not guaranteed to return ids in the same order).
    /// Any mst id absent from the tour lookup is left unresolved rather than
    /// silently plotted at the origin: it's dropped from drawing, its edges
    /// are dropped too, and the count surfaces as a caption warning.
    static func buildLayout(tour: VizTour, mst: VizMST) -> TopologyLayout {
        var lookup: [String: (Double, Double)] = [:]
        lookup.reserveCapacity(tour.ids.count)
        for (index, id) in tour.ids.enumerated() {
            let row = tour.coords[index]
            lookup[id] = (Double(row[0]), Double(row[1]))
        }

        var positions: [(x: Double, y: Double)?] = []
        positions.reserveCapacity(mst.ids.count)
        var missing = 0
        var minX = Double.greatestFiniteMagnitude, maxX = -Double.greatestFiniteMagnitude
        var minY = Double.greatestFiniteMagnitude, maxY = -Double.greatestFiniteMagnitude
        for id in mst.ids {
            if let position = lookup[id] {
                positions.append(position)
                minX = min(minX, position.0); maxX = max(maxX, position.0)
                minY = min(minY, position.1); maxY = max(maxY, position.1)
            } else {
                positions.append(nil)
                missing += 1
            }
        }
        if minX > maxX { minX = 0; maxX = 1; minY = 0; maxY = 1 }

        // Order preserved by compactMap, so still ascending by d.
        let edges: [(i: Int, j: Int, d: Double)] = mst.edges.compactMap { edge in
            guard positions.indices.contains(edge.i), positions.indices.contains(edge.j),
                  positions[edge.i] != nil, positions[edge.j] != nil else { return nil }
            return (edge.i, edge.j, edge.d)
        }

        let maxDistance = max(edges.last?.d ?? 0, 0.0001)
        return TopologyLayout(
            positions: positions, edges: edges, maxDistance: maxDistance,
            missingIDCount: missing, minX: minX, maxX: maxX, minY: minY, maxY: maxY
        )
    }

    private func draw(layout: TopologyLayout, threshold: Double,
                      in context: GraphicsContext, size: CGSize) {
        guard !layout.positions.isEmpty else { return }
        let transform = PointTransform(
            minX: layout.minX, maxX: layout.maxX, minY: layout.minY, maxY: layout.maxY,
            size: size
        )

        let components = incremental?.components(at: threshold)
            ?? TopologyComponents.components(count: layout.positions.count, edges: layout.edges, threshold: threshold)

        var sizes: [Int: Int] = [:]
        for component in components { sizes[component, default: 0] += 1 }
        let ranked = sizes.filter { $0.value > 1 }
            .sorted { $0.value > $1.value }
            .map(\.key)
        var rankOf: [Int: Int] = [:]
        rankOf.reserveCapacity(ranked.count)
        for (index, component) in ranked.enumerated() { rankOf[component] = index }

        func color(for component: Int) -> Color {
            guard let size = sizes[component], size > 1, let rank = rankOf[component] else {
                return .white.opacity(0.25)
            }
            let hue = Double(rank % 12) / 12.0
            return Color(hue: hue, saturation: 0.72, brightness: 0.98)
        }

        for edge in layout.edges where edge.d <= threshold {
            guard let a2 = layout.positions[edge.i], let b2 = layout.positions[edge.j] else { continue }
            let a = transform.place(x: a2.x, y: a2.y)
            let b = transform.place(x: b2.x, y: b2.y)
            guard transform.isVisible(a, in: size, margin: 20) || transform.isVisible(b, in: size, margin: 20)
            else { continue }
            var path = Path()
            path.move(to: a)
            path.addLine(to: b)
            context.stroke(path, with: .color(.white.opacity(0.14)), lineWidth: 0.6)
        }

        for index in layout.positions.indices {
            guard let position = layout.positions[index] else { continue }
            let p = transform.place(x: position.x, y: position.y)
            guard transform.isVisible(p, in: size, margin: 6) else { continue }
            context.fill(
                Path(ellipseIn: CGRect(x: p.x - 1.4, y: p.y - 1.4, width: 2.8, height: 2.8)),
                with: .color(color(for: components[index]))
            )
        }
    }

    /// H0 persistence diagram: bucketed to the strip's pixel height so it
    /// stays legible at any edge count (the real corpus has ~2640 edges,
    /// far more than a 46pt-tall strip can draw one row per edge). Each row
    /// covers a contiguous slice of the sorted, ascending edge weights and
    /// draws the slice's max — an honest downsample, never a fabricated
    /// value, so the longest (most significant) merge in each slice always
    /// shows. A vertical cursor marks the current threshold.
    /// Downsamples ascending-sorted edge weights to at most `rowCount` bars,
    /// each the max of its slice — an honest downsample (never a fabricated
    /// value) so the strip stays legible at any edge count instead of every
    /// bar clamping to a fraction of a pixel (finding 1: real corpus has
    /// ~2640 edges into a 46pt-tall strip). `internal` so it's exercised
    /// directly by `TopologyBarcodeTests`.
    static func bucketedDeaths(_ sortedDistances: [Double], rowCount: Int) -> [Double] {
        guard !sortedDistances.isEmpty, rowCount > 0 else { return [] }
        let rows = min(sortedDistances.count, rowCount)
        var result: [Double] = []
        result.reserveCapacity(rows)
        for row in 0..<rows {
            let start = row * sortedDistances.count / rows
            let end = max(start + 1, (row + 1) * sortedDistances.count / rows)
            result.append(sortedDistances[start..<min(end, sortedDistances.count)].max() ?? 0)
        }
        return result
    }

    private func barcode(layout: TopologyLayout?) -> some View {
        let edges = layout?.edges ?? []
        let maxDistance = layout?.maxDistance ?? 0.0001
        return VStack(alignment: .leading, spacing: 4) {
            Text("H0 persistence \u{2014} bucketed merges, bar length = death (edge weight)")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Canvas { ctx, size in
                guard !edges.isEmpty, size.height > 0 else { return }
                let bars = Self.bucketedDeaths(edges.map(\.d), rowCount: Int(size.height))
                guard !bars.isEmpty else { return }
                let rowHeight = size.height / CGFloat(bars.count)
                for (row, bucketMax) in bars.enumerated() {
                    let y = CGFloat(row) * rowHeight
                    let width = max(CGFloat(bucketMax / maxDistance) * size.width, 1)
                    ctx.fill(Path(CGRect(x: 0, y: y, width: width, height: max(rowHeight - 0.5, 0.5))),
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
