//
//  TopologyLayoutTests.swift
//  HackathonTests
//
//  Review fix tests: (4) a tour/mst id mismatch must drop the affected
//  points and edges rather than silently plotting them at the origin, and
//  (1) the barcode strip must stay legible (bounded row count, honest
//  downsample) at real corpus scale (~2640 edges).
//

import Foundation
import Testing
@testable import Hackathon

struct TopologyLayoutTests {
    /// base64 of little-endian float32, 3 rows x 8 cols: e0=(1,0,...),
    /// e1=(0,1,0,...), origin — ids "a", "b", "c" in that order.
    private static let coords8Base64 =
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIA/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

    private func makeTour(ids: [String]) throws -> VizTour {
        let idList = ids.map { "\"\($0)\"" }.joined(separator: ",")
        let json = """
        { "ids": [\(idList)], "coords8": "\(Self.coords8Base64)",
          "variance": [0.5, 0.3, 0.2, 0, 0, 0, 0, 0] }
        """
        return try JSONDecoder().decode(VizTour.self, from: Data(json.utf8))
    }

    private func makeMST(ids: [String], edges: [(Int, Int, Double)]) throws -> VizMST {
        let idList = ids.map { "\"\($0)\"" }.joined(separator: ",")
        let edgeList = edges.map { "[\($0.0), \($0.1), \($0.2)]" }.joined(separator: ",")
        let json = """
        { "ids": [\(idList)], "edges": [\(edgeList)] }
        """
        return try JSONDecoder().decode(VizMST.self, from: Data(json.utf8))
    }

    // MARK: - Finding 4: missing-id guard

    @Test func everyMSTIDResolvedLeavesNoMissingCountAndAllEdges() throws {
        let tour = try makeTour(ids: ["a", "b", "c"])
        let mst = try makeMST(ids: ["a", "b", "c"], edges: [(0, 1, 0.1), (1, 2, 0.2)])

        let layout = TopologyView.buildLayout(tour: tour, mst: mst)

        #expect(layout.missingIDCount == 0)
        #expect(layout.positions.allSatisfy { $0 != nil })
        #expect(layout.edges.count == 2)
    }

    @Test func mstIDMissingFromTourIsDroppedNotPlottedAtOrigin() throws {
        // "z" is in the mst snapshot but not in the tour snapshot.
        let tour = try makeTour(ids: ["a", "b", "c"])
        let mst = try makeMST(
            ids: ["a", "b", "z"],
            edges: [(0, 1, 0.1), (1, 2, 0.2)]
        )

        let layout = TopologyView.buildLayout(tour: tour, mst: mst)

        #expect(layout.missingIDCount == 1)
        #expect(layout.positions[0] != nil)
        #expect(layout.positions[1] != nil)
        #expect(layout.positions[2] == nil, "unresolved id must not fall back to (0, 0)")
        // Edge 1-2 touches the unresolved point and must be dropped, not
        // drawn as a fake edge into the origin.
        #expect(layout.edges.count == 1)
        #expect(layout.edges[0].i == 0 && layout.edges[0].j == 1)
    }

    // MARK: - Finding 1: barcode legibility at real corpus scale

    @Test func bucketedDeathsStaysWithinStripHeightAtRealCorpusScale() {
        // Real live count from the review: 2639 MST edges, ascending.
        let distances = (0..<2639).map { Double($0) / 2639.0 }
        let bars = TopologyView.bucketedDeaths(distances, rowCount: 46)

        #expect(bars.count == 46, "must downsample to the strip's row budget, not one bar per edge")
        // Honest downsample: the last bucket's max must be the true overall
        // max (the most significant, longest-lived merge is never hidden).
        #expect(bars.last == distances.last)
        #expect(bars.first == distances[0..<(2639 / 46)].max())
    }

    @Test func bucketedDeathsIsNonDecreasingSinceInputIsSortedAscending() {
        let distances = (0..<2639).map { Double($0) / 2639.0 }
        let bars = TopologyView.bucketedDeaths(distances, rowCount: 46)
        for i in 1..<bars.count {
            #expect(bars[i] >= bars[i - 1])
        }
    }

    @Test func bucketedDeathsWithFewerEdgesThanRowsIsOneBarPerEdge() {
        let distances = [0.1, 0.2, 0.3]
        let bars = TopologyView.bucketedDeaths(distances, rowCount: 46)
        #expect(bars == distances)
    }

    @Test func bucketedDeathsOfEmptyInputIsEmpty() {
        #expect(TopologyView.bucketedDeaths([], rowCount: 46).isEmpty)
    }
}
