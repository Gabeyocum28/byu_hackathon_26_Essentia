//
//  CombinedSeed.swift
//  Hackathon
//
//  Several chosen songs, carried through the app as one ordinary Track.
//
//  GET /recommend takes a comma-separated track_id and ranks against the
//  centroid of those songs' embeddings. Packing the selection into a single
//  Track means the rest of the flow — SeedView, the axis buttons,
//  RecommendationsView — keeps treating it as any other seed, so multi-select
//  needs no new screen, no new endpoint and no second code path.
//

import Foundation

extension Track {
    /// One seed standing for every selected track, or nil if none are.
    ///
    /// A single selection returns that track untouched: one song is not a
    /// special case of the centroid, it *is* the centroid.
    static func combined(_ tracks: [Track]) -> Track? {
        guard let first = tracks.first else { return nil }
        guard tracks.count > 1 else { return first }
        return Track(
            trackID: tracks.map(\.trackID).joined(separator: ","),
            title: "\(tracks.count) songs",
            artist: tracks.map(\.artist).joined(separator: ", "),
            album: "",
            artworkURL: first.artworkURL,
            previewURL: nil,        // a centroid has no audio of its own
            score: nil
        )
    }

    /// The individual track ids behind this seed.
    ///
    /// One element for an ordinary track, several for a combined one. Used
    /// where each song must be handled separately — POST /seed analyzes one
    /// track at a time.
    var seedIDs: [String] {
        trackID.split(separator: ",").map(String.init)
    }

    /// Whether this seed stands for more than one song.
    var isCombined: Bool { seedIDs.count > 1 }
}
