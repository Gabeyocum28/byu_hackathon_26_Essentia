//
//  TopologyComponentsTests.swift
//  HackathonTests
//
//  Union-find over a handcrafted MST edge list: components at a threshold
//  should match single-linkage clustering by hand.
//

import Testing
@testable import Hackathon

struct TopologyComponentsTests {
    // 5 points, 4 edges (a spanning tree), ascending by distance:
    // 0-1 (0.1), 1-2 (0.2), 3-4 (0.3), 2-3 (0.6)
    private let edges: [(i: Int, j: Int, d: Double)] = [
        (0, 1, 0.1), (1, 2, 0.2), (3, 4, 0.3), (2, 3, 0.6),
    ]

    @Test func zeroThresholdLeavesEverySingleton() {
        let components = TopologyComponents.components(count: 5, edges: edges, threshold: 0)
        #expect(Set(components).count == 5)
    }

    @Test func thresholdBelowAnEdgeGroupsOnlyThatMerge() {
        let components = TopologyComponents.components(count: 5, edges: edges, threshold: 0.15)
        #expect(components[0] == components[1])
        #expect(components[2] != components[0])
        #expect(components[3] != components[4])
    }

    @Test func thresholdBetweenSecondAndThirdEdgeMergesOnlyTheFirstTwoEdges() {
        // 0.25 admits 0-1 (0.1) and 1-2 (0.2) but not 3-4 (0.3): a trio plus
        // two still-separate singletons.
        let components = TopologyComponents.components(count: 5, edges: edges, threshold: 0.25)
        #expect(components[0] == components[1])
        #expect(components[1] == components[2])
        #expect(components[3] != components[4])
        #expect(components[0] != components[3])
    }

    @Test func thresholdAboveEveryEdgeMergesAllIntoOneComponent() {
        let components = TopologyComponents.components(count: 5, edges: edges, threshold: 1.0)
        #expect(Set(components).count == 1)
    }

    @Test func unionFindPathCompressionKeepsFindConsistentAfterManyUnions() {
        var uf = UnionFind(count: 6)
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(3, 4)
        uf.union(4, 5)
        #expect(uf.find(0) == uf.find(2))
        #expect(uf.find(3) == uf.find(5))
        #expect(uf.find(0) != uf.find(3))
        uf.union(2, 3)
        #expect(uf.find(0) == uf.find(5))
    }

    // MARK: - IncrementalTopologyComponents (review finding 3: don't redo
    // union-find from scratch on every slider tick)

    /// Two nodes are "the same component" iff the partition (the set of
    /// same-vs-different pairs) matches — root *labels* between the
    /// reference and incremental implementations aren't required to match,
    /// only which points share a root.
    private func partitionsMatch(_ a: [Int], _ b: [Int]) -> Bool {
        guard a.count == b.count else { return false }
        for i in 0..<a.count {
            for j in 0..<a.count {
                guard (a[i] == a[j]) == (b[i] == b[j]) else { return false }
            }
        }
        return true
    }

    @Test func incrementalMatchesReferenceAcrossRisingThresholds() {
        var incremental = IncrementalTopologyComponents(count: 5, sortedEdges: edges)
        for threshold in [0.0, 0.15, 0.25, 0.3, 1.0] {
            let reference = TopologyComponents.components(count: 5, edges: edges, threshold: threshold)
            let got = incremental.components(at: threshold)
            #expect(partitionsMatch(got, reference), "mismatch at threshold \(threshold)")
        }
    }

    @Test func incrementalMatchesReferenceWhenThresholdMovesBackward() {
        var incremental = IncrementalTopologyComponents(count: 5, sortedEdges: edges)
        _ = incremental.components(at: 1.0)
        #expect(incremental.appliedEdgeCount == 4)

        let got = incremental.components(at: 0.15)
        let reference = TopologyComponents.components(count: 5, edges: edges, threshold: 0.15)
        #expect(partitionsMatch(got, reference))
        #expect(incremental.appliedEdgeCount == 1)
    }

    @Test func incrementalOnlyUnionsNewlyAdmittedEdgesGoingForward() {
        var incremental = IncrementalTopologyComponents(count: 5, sortedEdges: edges)
        _ = incremental.components(at: 0.15)
        #expect(incremental.appliedEdgeCount == 1)
        _ = incremental.components(at: 0.25)
        #expect(incremental.appliedEdgeCount == 2)
        // Threshold stayed within the same admitted-edge bracket: no rework.
        _ = incremental.components(at: 0.29)
        #expect(incremental.appliedEdgeCount == 2)
    }

    @Test func edgeCountBinarySearchMatchesLinearScan() {
        let distances = edges.map(\.d)
        for threshold in [-1.0, 0.0, 0.05, 0.1, 0.2, 0.25, 0.3, 0.6, 5.0] {
            let expected = distances.filter { $0 <= threshold }.count
            #expect(IncrementalTopologyComponents.edgeCount(upTo: threshold, in: edges) == expected)
        }
    }
}
