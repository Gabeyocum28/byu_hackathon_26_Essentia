//
//  InsightsInteractionTests.swift
//  HackathonTests
//
//  Interaction intent tests for the Insights screen.
//

import Foundation
import Testing
@testable import Hackathon

@MainActor
struct InsightsInteractionTests {
    private let seed = Track(
        trackID: "seed", title: "Seed", artist: "Artist", album: "Album",
        artworkURL: nil, previewURL: nil, score: nil
    )

    private let rec = VizMap.Rec(
        trackID: "rec", title: "Recommendation", artist: "Artist",
        album: "Album", artworkURL: nil, previewURL: nil, score: 0.91,
        x: 0.2, y: -0.3, groove: nil,
        math: VizMap.ScoreMath(
            metric: "cosine", dot: 0.91, seedNorm: 1, recNorm: 1,
            distance: nil, centrality: nil
        )
    )

    @Test func selectingArtworkAlsoRequestsPlaybackForThatTrack() {
        let model = InsightsModel(
            seed: seed,
            axis: Axis(id: "sounds_like", label: "Sounds like this")
        )
        var requestedTrack: Track?

        model.selectAndPlay(rec) { requestedTrack = $0 }

        #expect(model.selected?.trackID == "rec")
        #expect(requestedTrack?.trackID == "rec")
    }

    @Test func seekingClampsProgressToPreviewBounds() {
        let playback = PlaybackController()

        playback.seek(progress: -0.4)
        #expect(playback.progress == 0)

        playback.seek(progress: 0.37)
        #expect(playback.progress == 0.37)

        playback.seek(progress: 1.4)
        #expect(playback.progress == 1)
    }
}
