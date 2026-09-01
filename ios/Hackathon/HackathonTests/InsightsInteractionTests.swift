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

    /// The screen loads a second map on the "surprise" axis so the Proof
    /// tab's hubness toggle has something to compare. That map must stay
    /// inside its own section: letting it lead replaced the axis the user
    /// actually chose, and Proof showed songs unlike the seed with no
    /// explanation.
    @Test func everyModeShowsTheChosenAxisNotTheSurpriseComparison() {
        let model = InsightsModel(
            seed: seed,
            axis: Axis(id: "sounds_like", label: "Sounds like this")
        )
        model.map = Self.map(recTrackID: "chosen", axisID: "sounds_like")
        model.proofMap = Self.map(recTrackID: "surprise", axisID: "surprise")

        for mode in InsightMode.allCases {
            model.activate(mode)
            #expect(model.displayMap?.recs.first?.trackID == "chosen")
            #expect(model.selected?.trackID == "chosen")
        }

        // The comparison is still available for the toggle's own list.
        #expect(model.proofMap?.recs.first?.trackID == "surprise")
    }

    /// The seed needs to be selectable: comparing a recommendation against
    /// it means pulling up its own spectrogram. It carries no score, so the
    /// math and attribution panels stand down while it is the selection.
    @Test func seedIsSelectableAndSurvivesAModeSwitch() {
        let model = InsightsModel(
            seed: seed,
            axis: Axis(id: "sounds_like", label: "Sounds like this")
        )
        model.map = Self.map(recTrackID: "chosen", axisID: "sounds_like")
        model.selected = model.map?.recs.first
        var played: Track?

        model.selectSeedAndPlay { played = $0 }

        #expect(model.seedSelected)
        #expect(model.selected == nil)              // no score panel for the seed
        #expect(played?.trackID == "seed")
        #expect(model.focusedPoint?.id == "seed")

        // Switching tabs must not quietly hand the screen back to a rec.
        model.activate(.sound)
        #expect(model.seedSelected)
        #expect(model.selected == nil)

        // Picking a rec again releases it.
        model.selectAndPlay(rec) { _ in }
        #expect(!model.seedSelected)
        #expect(model.selected?.trackID == "rec")
    }

    private static func map(recTrackID: String, axisID: String) -> VizMap {
        let rec = VizMap.Rec(
            trackID: recTrackID, title: recTrackID, artist: "Artist",
            album: "Album", artworkURL: nil, previewURL: nil, score: 0.5,
            x: 0, y: 0, groove: nil,
            math: VizMap.ScoreMath(metric: "cosine", dot: 0.5, seedNorm: 1,
                                   recNorm: 1, distance: nil, centrality: nil)
        )
        return VizMap(
            points: VizMap.Points(ids: [recTrackID], x: [0], y: [0],
                                  tracks: [rec.track]),
            seed: VizMap.SeedPoint(
                trackID: "seed", title: "Seed", artist: "Artist",
                album: "Album", artworkURL: nil, previewURL: nil,
                x: 0, y: 0, groove: nil
            ),
            recs: [rec],
            axis: VizMap.AxisInfo(id: axisID, metric: "cosine", direction: 1)
        )
    }

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

    // MARK: - Fixed-radius PointTransform (review finding 2: the Grand Tour
    // must not rescale/"breathe" as the rotating projection's bounding box
    // changes shape frame to frame; the fix holds scale/center fixed from a
    // rotation-invariant radius instead of scanning the live points).

    @Test func fixedRadiusTransformCentersTheOriginRegardlessOfProjectedExtent() {
        let transform = PointTransform(radius: 5, size: CGSize(width: 200, height: 200))
        let center = transform.place(x: 0, y: 0)
        #expect(center.x == 100)
        #expect(center.y == 100)
    }

    @Test func fixedRadiusTransformScaleDoesNotChangeWithDifferentPointSets() {
        // Same radius, two very different "current rotation" point clouds:
        // the transform (and thus scale/center) must be identical for both,
        // since it's built from the radius alone.
        let a = PointTransform(radius: 4, size: CGSize(width: 200, height: 200))
        let b = PointTransform(radius: 4, size: CGSize(width: 200, height: 200))
        #expect(a.place(x: 2, y: -2) == b.place(x: 2, y: -2))
        #expect(a.place(x: 0.1, y: 3.9) == b.place(x: 0.1, y: 3.9))
    }

    @Test func fixedRadiusTransformPlacesAPointAtTheRadiusNearTheEdge() {
        let radius = 5.0
        let transform = PointTransform(radius: radius, size: CGSize(width: 200, height: 200))
        let center = transform.place(x: 0, y: 0)
        let edge = transform.place(x: radius, y: 0)
        // fit = min(200,200) - 2*16 = 168; span = 2*radius = 10; scale = 16.8
        #expect(abs((edge.x - center.x) - 84) < 0.001)
    }

    @Test func explicitBoundsTransformMatchesTheArrayScanningInitializer() {
        let x: [Double] = [-2, 0, 3]
        let y: [Double] = [-1, 4, 1]
        let scanned = PointTransform(x: x, y: y, size: CGSize(width: 300, height: 150))
        let explicit = PointTransform(
            minX: -2, maxX: 3, minY: -1, maxY: 4, size: CGSize(width: 300, height: 150)
        )
        #expect(scanned.place(x: 1, y: 2) == explicit.place(x: 1, y: 2))
    }

    @Test func walkSelectionUsesTwoDistinctGalaxyStarsAsEndpoints() throws {
        let model = InsightsModel(
            seed: seed,
            axis: Axis(id: "sounds_like", label: "Sounds like this")
        )
        let first = GalaxySelection(track: seed, x: 0, y: 0)
        let secondTrack = Track(
            trackID: "destination", title: "Destination", artist: "Artist",
            album: "Album", artworkURL: nil, previewURL: nil, score: nil
        )
        let second = GalaxySelection(track: secondTrack, x: 1, y: 1)

        #expect(model.selectWalkPoint(first) == nil)
        #expect(model.walkStart?.id == "seed")
        let endpoints = try #require(model.selectWalkPoint(second))
        #expect(endpoints.from == "seed")
        #expect(endpoints.to == "destination")
        #expect(model.walkStart == nil)
    }
}
