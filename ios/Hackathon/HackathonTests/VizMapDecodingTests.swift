//
//  VizMapDecodingTests.swift
//  HackathonTests
//
//  GET /viz/map payload (non-contract demo endpoint) decodes into VizMap.
//

import Foundation
import Testing
@testable import Hackathon

struct VizMapDecodingTests {

    static let json = """
    {
      "points": { "ids": ["1", "2", "3"], "x": [0.1, -0.2, 0.3], "y": [0.0, 0.5, -0.5] },
      "seed": {
        "track_id": "1", "title": "So What", "artist": "Miles Davis",
        "album": "Kind of Blue", "artwork_url": "https://a.jpg",
        "preview_url": "https://a.mp3",
        "x": 0.1, "y": 0.0, "groove": [136.0, 0.92, 3.1, 0.56]
      },
      "recs": [
        {
          "track_id": "2", "title": "Freddie Freeloader", "artist": "Miles Davis",
          "album": "Kind of Blue", "artwork_url": "https://b.jpg",
          "preview_url": "https://b.mp3", "score": 0.91,
          "x": -0.2, "y": 0.5, "groove": [135.0, 0.9, 2.9, 0.6],
          "math": { "metric": "cosine", "dot": 11.2, "seed_norm": 3.5,
                    "rec_norm": 3.52, "distance": null, "centrality": null }
        }
      ],
      "axis": { "id": "sounds_like", "metric": "cosine", "direction": 1 }
    }
    """

    @Test func decodesFullPayload() throws {
        let map = try JSONDecoder().decode(VizMap.self, from: Data(Self.json.utf8))
        #expect(map.points.ids == ["1", "2", "3"])
        #expect(map.points.x.count == 3)
        #expect(map.seed.trackID == "1")
        #expect(map.seed.groove?.count == 4)
        #expect(map.recs.count == 1)
        #expect(map.axis.metric == "cosine")
        #expect(map.axis.direction == 1)

        let rec = try #require(map.recs.first)
        #expect(rec.trackID == "2")
        #expect(rec.score == 0.91)
        #expect(rec.math.dot == 11.2)
        #expect(rec.math.distance == nil)
        #expect(rec.track.title == "Freddie Freeloader")
    }
}
