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
}
