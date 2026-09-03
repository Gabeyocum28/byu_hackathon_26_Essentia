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

    /// Songs picked for a combined seed, in the order they were chosen.
    ///
    /// Kept here rather than in the view so it survives a new search: building
    /// a set of five songs means searching five times, and a selection that
    /// emptied on every query would make that impossible.
    var selected: [Track] = []

    private let api: APIClient

    init(api: APIClient = .shared) {
        self.api = api
    }

    func isSelected(_ track: Track) -> Bool {
        selected.contains { $0.trackID == track.trackID }
    }

    func toggle(_ track: Track) {
        if let at = selected.firstIndex(where: { $0.trackID == track.trackID }) {
            selected.remove(at: at)
        } else {
            selected.append(track)
        }
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
                            SelectToggle(isOn: model.isSelected(track)) {
                                model.toggle(track)
                            }
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
            .safeAreaInset(edge: .bottom) {
                // Only present once something is chosen, so the ordinary
                // one-song flow (tap the row) looks exactly as it did.
                if let seed = Track.combined(model.selected) {
                    SelectionBar(count: model.selected.count, seed: seed) {
                        model.selected.removeAll()
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

/// The tick that adds a track to the combined seed.
private struct SelectToggle: View {
    let isOn: Bool
    let toggle: () -> Void

    var body: some View {
        Button(action: toggle) {
            Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
                .font(.title3)
                .foregroundStyle(isOn ? Color.accentColor : Color.secondary)
        }
        // .plain so the tap does not also fire the row's NavigationLink.
        .buttonStyle(.plain)
        .accessibilityLabel(isOn ? "Deselect" : "Select")
    }
}

/// Appears while songs are selected: how many, clear, and go.
private struct SelectionBar: View {
    let count: Int
    let seed: Track
    let clear: () -> Void

    var body: some View {
        HStack {
            Text("\(count) selected")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Button("Clear", action: clear)
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            NavigationLink(value: seed) {
                Text("Find similar")
                    .font(.headline)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(.tint, in: .rect(cornerRadius: 10))
                    .foregroundStyle(.white)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(.bar)
    }
}
