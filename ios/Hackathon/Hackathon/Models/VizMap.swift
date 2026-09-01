//
//  VizMap.swift
//  Hackathon
//
//  Payload of GET /viz/map — the demo/debug endpoint behind the Insights
//  screen. Not part of contract/contract.md: the whole corpus as 2D points
//  (PCA of embedding space), the seed, and the recs with the numbers behind
//  each score.
//

import Foundation

nonisolated struct VizMap: Decodable {
    struct Points: Decodable {
        let ids: [String]
        let x: [Double]
        let y: [Double]
    }

    /// The seed's contract fields plus its position and groove vector.
    struct SeedPoint: Decodable {
        let trackID: String
        let title: String
        let artist: String
        let album: String
        let artworkURL: URL?
        let previewURL: URL?
        let x: Double
        let y: Double
        let groove: [Double]?

        var track: Track {
            Track(trackID: trackID, title: title, artist: artist, album: album,
                  artworkURL: artworkURL, previewURL: previewURL, score: nil)
        }

        enum CodingKeys: String, CodingKey {
            case trackID = "track_id"
            case title, artist, album
            case artworkURL = "artwork_url"
            case previewURL = "preview_url"
            case x, y, groove
        }
    }

    /// One recommendation with its position, groove, and score arithmetic.
    struct Rec: Decodable, Identifiable {
        let trackID: String
        let title: String
        let artist: String
        let album: String
        let artworkURL: URL?
        let previewURL: URL?
        let score: Double
        let x: Double
        let y: Double
        let groove: [Double]?
        let math: ScoreMath

        var id: String { trackID }

        var track: Track {
            Track(trackID: trackID, title: title, artist: artist, album: album,
                  artworkURL: artworkURL, previewURL: previewURL, score: score)
        }

        enum CodingKeys: String, CodingKey {
            case trackID = "track_id"
            case title, artist, album
            case artworkURL = "artwork_url"
            case previewURL = "preview_url"
            case score, x, y, groove, math
        }
    }

    /// cosine: score = dot / (seedNorm * recNorm)
    /// euclidean: score = 1 / (1 + distance)
    struct ScoreMath: Decodable {
        let metric: String
        let dot: Double
        let seedNorm: Double
        let recNorm: Double
        let distance: Double?
        let centrality: Double?

        enum CodingKeys: String, CodingKey {
            case metric, dot
            case seedNorm = "seed_norm"
            case recNorm = "rec_norm"
            case distance, centrality
        }
    }

    struct AxisInfo: Decodable {
        let id: String
        let metric: String
        let direction: Int
    }

    let points: Points
    let seed: SeedPoint
    let recs: [Rec]
    let axis: AxisInfo
}
