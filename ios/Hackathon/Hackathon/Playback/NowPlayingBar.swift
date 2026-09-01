//
//  NowPlayingBar.swift
//  Hackathon
//
//  The persistent play bar. Sits under the whole navigation stack so a preview
//  keeps playing while you move between search, seed and recommendations.
//

import SwiftUI

/// Play/pause control for one track, shared by list rows and the play bar.
struct PlayButton: View {
    @Environment(PlaybackController.self) private var playback
    let track: Track

    private var isCurrent: Bool { playback.nowPlayingID == track.id }
    private var isFailed: Bool { isCurrent && playback.errorMessage != nil }

    var body: some View {
        Button {
            playback.toggle(track)
        } label: {
            Group {
                if isCurrent && playback.isLoading {
                    ProgressView()
                } else {
                    Image(systemName: symbol)
                        .font(.title2)
                        .foregroundStyle(isFailed ? AnyShapeStyle(.red) : AnyShapeStyle(.tint))
                }
            }
            .frame(width: 32, height: 32)
            .contentShape(.rect)
        }
        // .borderless keeps the tap off the surrounding row/NavigationLink.
        .buttonStyle(.borderless)
    }

    private var symbol: String {
        guard isCurrent else { return "play.circle" }
        if playback.errorMessage != nil { return "exclamationmark.circle" }
        return playback.isPlaying ? "pause.circle.fill" : "play.circle"
    }
}

struct NowPlayingBar: View {
    @Environment(PlaybackController.self) private var playback

    var body: some View {
        if let track = playback.nowPlaying {
            VStack(spacing: 0) {
                GeometryReader { geo in
                    Rectangle()
                        .fill(.tint)
                        .frame(width: geo.size.width * playback.progress)
                }
                .frame(height: 2)
                .background(.quaternary)

                HStack(spacing: 12) {
                    Artwork(url: track.artworkURL)
                        .frame(width: 44, height: 44)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(track.title)
                            .font(.subheadline.weight(.medium))
                            .lineLimit(1)
                        Text(playback.errorMessage ?? track.artist)
                            .font(.caption)
                            .foregroundStyle(
                                playback.errorMessage == nil
                                    ? AnyShapeStyle(.secondary)
                                    : AnyShapeStyle(.red)
                            )
                            .lineLimit(1)
                    }

                    Spacer(minLength: 0)

                    PlayButton(track: track)

                    Button {
                        playback.stop()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.borderless)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            }
            .background(.bar)
        }
    }
}
