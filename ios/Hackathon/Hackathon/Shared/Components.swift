//
//  Components.swift
//  Hackathon
//
//  Small shared views used across the feature screens.
//

import SwiftUI

/// Square album artwork with a graceful placeholder.
struct Artwork: View {
    let url: URL?

    var body: some View {
        AsyncImage(url: url) { phase in
            switch phase {
            case .success(let image):
                image.resizable().scaledToFill()
            default:
                Rectangle()
                    .fill(.quaternary)
                    .overlay {
                        Image(systemName: "music.note")
                            .foregroundStyle(.secondary)
                    }
            }
        }
        .clipShape(.rect(cornerRadius: 8))
    }
}

/// Compact title + artist row with small artwork, used in lists.
struct TrackRow: View {
    let track: Track

    var body: some View {
        HStack(spacing: 12) {
            Artwork(url: track.artworkURL)
                .frame(width: 56, height: 56)
            VStack(alignment: .leading, spacing: 2) {
                Text(track.title)
                    .lineLimit(1)
                Text(track.artist)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }
}

/// Large seed header shown at the top of the axis-selection screen.
struct TrackHeader: View {
    let track: Track

    var body: some View {
        VStack(spacing: 12) {
            Artwork(url: track.artworkURL)
                .frame(width: 160, height: 160)
            VStack(spacing: 4) {
                Text(track.title)
                    .font(.title3.weight(.semibold))
                    .multilineTextAlignment(.center)
                Text(track.artist)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

/// Simple error + retry affordance.
struct RetryView: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Text(message)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("Try Again", action: retry)
                .buttonStyle(.bordered)
        }
    }
}
