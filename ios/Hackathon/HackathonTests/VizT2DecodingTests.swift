//
//  VizT2DecodingTests.swift
//  HackathonTests
//
//  Decoding tests for the Tour, Topology, and eigen-listening payloads.
//

import Foundation
import Testing
@testable import Hackathon

struct VizT2DecodingTests {
    /// base64 of little-endian float32, 3 rows x 8 cols:
    /// [0.1...0.8], [1.1...1.8], [-0.5...0.2]
    private static let coords8Base64 =
        "zczMPc3MTD6amZk+zczMPgAAAD+amRk/MzMzP83MTD/NzIw/mpmZP2Zmpj8zM7M/AADAP83MzD+amdk/ZmbmPwAAAL/NzMy+mpmZvs3MTL7NzMy9AAAAAM3MzD3NzEw+"

    @Test func decodesTourCoordsFromBase64FloatBlob() throws {
        let json = """
        { "ids": ["a", "b", "c"], "coords8": "\(Self.coords8Base64)",
          "variance": [0.3, 0.2, 0.1, 0.1, 0.1, 0.05, 0.03, 0.02] }
        """
        let tour = try JSONDecoder().decode(VizTour.self, from: Data(json.utf8))
        #expect(tour.ids == ["a", "b", "c"])
        #expect(tour.coords.count == 3)
        #expect(tour.coords[0].count == 8)
        #expect(abs(tour.coords[0][0] - 0.1) < 0.0001)
        #expect(abs(tour.coords[1][7] - 1.8) < 0.0001)
        #expect(abs(tour.coords[2][0] - (-0.5)) < 0.0001)
        #expect(abs(tour.variance.reduce(0, +) - 0.9) < 0.0001)
    }

    @Test func rejectsCoords8WhoseByteCountDoesNotMatchIDs() {
        // Same blob (3 rows) but ids claims 4 rows: must fail, not truncate.
        let json = """
        { "ids": ["a", "b", "c", "d"], "coords8": "\(Self.coords8Base64)",
          "variance": [0.5, 0.5] }
        """
        #expect(throws: (any Error).self) {
            try JSONDecoder().decode(VizTour.self, from: Data(json.utf8))
        }
    }

    @Test func decodesMSTEdgesAscendingByDistance() throws {
        let json = """
        { "ids": ["a", "b", "c"],
          "edges": [[0, 1, 0.05], [1, 2, 0.12]] }
        """
        let mst = try JSONDecoder().decode(VizMST.self, from: Data(json.utf8))
        #expect(mst.ids == ["a", "b", "c"])
        #expect(mst.edges.count == 2)
        #expect(mst.edges[0].i == 0 && mst.edges[0].j == 1)
        #expect(mst.edges[0].d == 0.05)
        #expect(mst.edges[1].d == 0.12)
    }

    @Test func decodesExtremesLowAndHighPlayableTracks() throws {
        let track = """
        "track_id": "1", "title": "Low Song", "artist": "A",
        "album": "Alb", "artwork_url": null, "preview_url": null
        """
        let json = """
        { "pc": 1, "variance_pct": 12.5,
          "low": [{ \(track) }], "high": [{ \(track) }] }
        """
        let extremes = try JSONDecoder().decode(VizExtremesResponse.self, from: Data(json.utf8))
        #expect(extremes.pc == 1)
        #expect(extremes.variancePct == 12.5)
        #expect(extremes.low.first?.track.title == "Low Song")
        #expect(extremes.high.first?.trackID == "1")
    }
}
