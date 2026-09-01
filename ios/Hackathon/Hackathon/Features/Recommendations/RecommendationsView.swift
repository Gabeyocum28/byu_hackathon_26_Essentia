//
//  RecommendationsView.swift
//  Hackathon
//
//  The recommendation list for a (seed, axis) pair. Each row plays its 30s
//  preview through the shared PlaybackController, which keeps playing in the
//  bar after you navigate away.
//

import SwiftUI

@MainActor
@Observable
final class RecommendationsModel {
    let seed: Track
    let axis: Axis
    var results: [Track] = []
    var isLoading = true
    var errorMessage: String?

    private let api: APIClient

    init(seed: Track, axis: Axis, api: APIClient = .shared) {
        self.seed = seed
        self.axis = axis
        self.api = api
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            results = try await api.recommend(trackID: seed.trackID, axis: axis.id)
        } catch {
            results = []
            errorMessage = "Couldn't load recommendations."
        }
        isLoading = false
    }
}

struct RecommendationsView: View {
    @State private var model: RecommendationsModel

    init(seed: Track, axis: Axis) {
        _model = State(initialValue: RecommendationsModel(seed: seed, axis: axis))
    }

    var body: some View {
        Group {
            if let errorMessage = model.errorMessage {
                RetryView(message: errorMessage) {
                    Task { await model.load() }
                }
            } else {
                List(model.results) { track in
                    PlayableTrackRow(track: track)
                }
                .overlay {
                    if model.isLoading { ProgressView() }
                }
            }
        }
        .navigationTitle(model.axis.label)
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load() }
    }
}

/// A track row with a play/pause control driving the shared player.
private struct PlayableTrackRow: View {
    let track: Track

    var body: some View {
        HStack {
            TrackRow(track: track)
            Spacer(minLength: 0)
            PlayButton(track: track)
        }
    }
}
