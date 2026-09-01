//
//  InsightsInteractionTests.swift
//  HackathonTests
//
//  Interaction intent tests for the Insights screen.
//

import Foundation
import CoreGraphics
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

    @Test func galaxyTransformAppliesZoomAndPanAroundViewCenter() {
        let transform = PointTransform(
            x: [-1, 1], y: [-1, 1], size: CGSize(width: 200, height: 100),
            zoom: 2, pan: CGSize(width: 10, height: -5)
        )

        let center = transform.place(x: 0, y: 0)
        let right = transform.place(x: 1, y: 0)

        #expect(center.x == 110)
        #expect(center.y == 45)
        #expect(right.x == 178)
        #expect(right.y == 45)
    }

    @Test func galaxyNearestPointSearchesWholeCorpusAndHonorsHitRadius() {
        let transform = PointTransform(
            x: [-1, 0, 1], y: [0, 0, 0],
            size: CGSize(width: 220, height: 100)
        )
        let target = transform.place(x: 0, y: 0)

        #expect(transform.nearestIndex(
            to: CGPoint(x: target.x + 3, y: target.y),
            x: [-1, 0, 1], y: [0, 0, 0], maximumDistance: 12
        ) == 1)
        #expect(transform.nearestIndex(
            to: CGPoint(x: target.x + 30, y: target.y + 30),
            x: [-1, 0, 1], y: [0, 0, 0], maximumDistance: 12
        ) == nil)
    }
}
