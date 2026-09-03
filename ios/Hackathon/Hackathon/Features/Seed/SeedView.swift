//
//  SeedView.swift
//  Hackathon
//
//  Shows the chosen seed, prepares it (POST /seed) while loading the axis
//  buttons (GET /axes) in parallel, then renders one button per axis. Buttons
//  are always whatever the server sends — never hardcoded.
//

import SwiftUI

@MainActor
@Observable
final class SeedModel {
    enum LoadState: Equatable {
        case preparing
        case ready
        case unanalyzed
        case failed
    }

    let seed: Track
    var state: LoadState = .preparing
    var axes: [Axis] = []

    private let api: APIClient

    init(seed: Track, api: APIClient = .shared) {
        self.seed = seed
        self.api = api
    }

    func prepare() async {
        state = .preparing
        do {
            // Absorb the blocking seed analysis while the axes load.
            async let axesList = api.axes()

            // A combined seed carries several ids; POST /seed takes one track
            // at a time, so each is prepared in turn. Sequential on purpose:
            // a cold track costs a preview download and a forward pass on the
            // server, and firing all of them at once is how a burst of
            // downloads gets throttled.
            var allReady = true
            for trackID in seed.seedIDs {
                let response = try await api.seed(trackID: trackID)
                if response.status != "ready" { allReady = false }
            }

            axes = try await axesList
            state = allReady ? .ready : .unanalyzed
        } catch {
            state = .failed
        }
    }
}

struct SeedView: View {
    @State private var model: SeedModel

    init(seed: Track) {
        _model = State(initialValue: SeedModel(seed: seed))
    }

    var body: some View {
        VStack(spacing: 32) {
            TrackHeader(track: model.seed)

            switch model.state {
            case .preparing:
                ProgressView("Analyzing track…")
            case .unanalyzed:
                RetryView(message: "This track hasn't been analyzed yet. Is the embed worker running?") {
                    Task { await model.prepare() }
                }
            case .failed:
                RetryView(message: "Couldn't prepare this track.") {
                    Task { await model.prepare() }
                }
            case .ready:
                AxisButtons(seed: model.seed, axes: model.axes)
            }

            Spacer()
        }
        .padding()
        .navigationTitle("Find Similar")
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.prepare() }
    }
}

/// One full-width button per axis returned by /axes.
private struct AxisButtons: View {
    let seed: Track
    let axes: [Axis]

    var body: some View {
        VStack(spacing: 12) {
            ForEach(axes) { axis in
                NavigationLink(value: Recommendation(seed: seed, axis: axis)) {
                    Text(axis.label)
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(.tint, in: .rect(cornerRadius: 12))
                        .foregroundStyle(.white)
                }
            }
        }
    }
}
