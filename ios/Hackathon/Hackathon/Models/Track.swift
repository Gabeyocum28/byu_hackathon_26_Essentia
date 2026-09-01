//
//  Track.swift
//  Hackathon
//
//  The uniform track shape from contract/contract.md. One struct, decoded
//  identically at every endpoint. `score` is present on /recommend results
//  only and is ignored by the v1 UI.
//

import Foundation

nonisolated struct Track: Identifiable, Decodable, Hashable {
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
        case title
        case artist
        case album
        case artworkURL = "artwork_url"
        case previewURL = "preview_url"
        case score
    }
}
