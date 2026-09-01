//
//  Models.swift
//  Hackathon
//
//  The two shapes the server sends. One `Track` decoded identically at every
//  endpoint (contract/contract.md), and one `Axis` per button.
//

import Foundation

/// Uniform track shape returned by /search, /seed, and /recommend.
/// `score` is present on recommendation results only and the v1 UI ignores it.
struct Track: Decodable, Identifiable, Hashable {
    let trackID: String
    let title: String
    let artist: String
    let album: String
    let artworkURL: URL?
    let previewURL: URL?
    let score: Double?

    var id: String { trackID }

    enum CodingKeys: String, CodingKey {
        case trackID = "track_id"
        case title, artist, album, score
        case artworkURL = "artwork_url"
        case previewURL = "preview_url"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        trackID = try c.decode(String.self, forKey: .trackID)
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        artist = try c.decodeIfPresent(String.self, forKey: .artist) ?? ""
        album = try c.decodeIfPresent(String.self, forKey: .album) ?? ""
        score = try c.decodeIfPresent(Double.self, forKey: .score)

        // Decoded as String and converted, not as URL directly: URL's Decodable
        // init throws on a malformed string, and the crawler emits "" when a
        // track has no album art. One missing cover should not fail the whole
        // response.
        artworkURL = (try c.decodeIfPresent(String.self, forKey: .artworkURL))
            .flatMap(URL.init(string:))
        previewURL = (try c.decodeIfPresent(String.self, forKey: .previewURL))
            .flatMap(URL.init(string:))
    }
}

/// One recommendation axis, rendered as a button. The list comes from
/// GET /axes and is never hardcoded — the server decides how many there are.
struct Axis: Decodable, Identifiable, Hashable {
    let id: String
    let label: String
}
