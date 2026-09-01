import Foundation
import Testing
@testable import Hackathon

struct VizT1DecodingTests {
    @Test func decodesWalkDistanceAndPlayableSteps() throws {
        let json = """
        { "path": [
          { "track_id": "1", "title": "A", "artist": "X", "album": "Z",
            "artwork_url": null, "preview_url": "https://e.com/a.mp3", "x": 0.1, "y": 0.2 },
          { "track_id": "2", "title": "B", "artist": "Y", "album": "Z",
            "artwork_url": null, "preview_url": "https://e.com/b.mp3", "x": 0.4, "y": 0.5 }
        ], "geodesic": 1.66, "ambient": 0.71, "detour": 2.338, "k": 8 }
        """
        let walk = try JSONDecoder().decode(VizWalk.self, from: Data(json.utf8))
        #expect(walk.path.map(\.trackID) == ["1", "2"])
        #expect(walk.path[1].track.title == "B")
        #expect(walk.detour == 2.338)
    }

    @Test func decodesHistogramAndNullModel() throws {
        let json = """
        { "bins": [-0.5, 0.0, 0.5], "counts": [1, 5, 3],
          "rec_scores": [0.91, 0.82], "percentile": 99.7,
          "null": { "mean": 0.0, "sd": 0.028 },
          "corpus": { "mean": 0.356, "sd": 0.116 } }
        """
        let histogram = try JSONDecoder().decode(
            VizHistogram.self, from: Data(json.utf8)
        )
        #expect(histogram.counts == [1, 5, 3])
        #expect(histogram.recScores == [0.91, 0.82])
        #expect(histogram.null.sd == 0.028)
    }

    @Test func decodesPlayableHubCategories() throws {
        let track = """
        "track_id": "1", "title": "KHE CALOR", "artist": "DANNA",
        "album": "A", "artwork_url": null, "preview_url": null
        """
        let json = """
        { "hubs": [{ \(track), "count": 47 }],
          "central": [{ \(track), "centrality": 0.51 }],
          "isolated": [{ \(track), "centrality": 0.03 }],
          "expected_k": 8, "all_counts": [{ "track_id": "1", "count": 47 }] }
        """
        let hubs = try JSONDecoder().decode(VizHubs.self, from: Data(json.utf8))
        #expect(hubs.hubs.first?.count == 47)
        #expect(hubs.central.first?.track.title == "KHE CALOR")
        #expect(hubs.expectedK == 8)
    }
}
