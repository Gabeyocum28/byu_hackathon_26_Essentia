//
//  SearchView.swift
//  Hackathon
//
//  Root screen: search tracks, then pick one as the seed. Also hosts the
//  NavigationStack and registers the push destinations for the whole flow.
//

import SwiftUI

@MainActor
@Observable
final class SearchModel {
    var query = ""
    var results: [Track] = []
    var isLoading = false
    var errorMessage: String?

    private let api: APIClient

    init(api: APIClient = .shared) {
        self.api = api
    }

    func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            results = []
            return
        }
        isLoading = true
        errorMessage = nil
        do {
            results = try await api.search(query: trimmed)
        } catch {
            results = []
            errorMessage = (error as? LocalizedError)?.errorDescription ?? String(describing: error)
            print("[Search] request failed: \(error)")
        }
        isLoading = false
    }
}

struct SearchView: View {
    @State private var model = SearchModel()

    var body: some View {
        NavigationStack {
            Group {
                if let errorMessage = model.errorMessage, model.results.isEmpty {
                    ContentUnavailableView("Something went wrong", systemImage: "wifi.slash", description: Text(errorMessage))
                } else {
                    List(model.results) { track in
                        HStack {
                            NavigationLink(value: track) {
                                TrackRow(track: track)
                            }
                            PlayButton(track: track)
                        }
                    }
                    .overlay {
                        if model.isLoading { ProgressView() }
                    }
                }
            }
            .navigationTitle("Essentia")
            .searchable(text: $model.query, prompt: "Search for a track")
            .onSubmit(of: .search) {
                Task { await model.search() }
            }
            .navigationDestination(for: Track.self) { seed in
                SeedView(seed: seed)
            }
            .navigationDestination(for: Recommendation.self) { rec in
                RecommendationsView(seed: rec.seed, axis: rec.axis)
            }
        }
    }
}
