//
//  PlaybackController.swift
//  Hackathon
//
//  Owns a single AVPlayer for 30-second preview playback. Only one preview
//  plays at a time; starting a new one stops the current. The URL is resolved
//  fresh at play time (see PreviewResolver) and the asset is loaded before the
//  UI claims to be playing, so a dead preview surfaces as an error instead of
//  a button that flips to "pause" over silence.
//

import AVFoundation
import Observation

@MainActor
@Observable
final class PlaybackController {
    /// The track loaded into the player, or nil when nothing is loaded.
    private(set) var nowPlaying: Track?
    /// True only once audio is actually running.
    private(set) var isPlaying = false
    /// True while the fresh URL is resolved and the asset loaded.
    private(set) var isLoading = false
    /// Set when a track could not be played; cleared on the next attempt.
    private(set) var errorMessage: String?
    /// 0...1 through the preview, for the now-playing bar's progress line.
    private(set) var progress: Double = 0

    /// The id of the loaded track, for rows asking "is this one mine?".
    var nowPlayingID: String? { nowPlaying?.id }

    private let resolver: PreviewResolver
    private var player: AVPlayer?
    private var endObserver: NSObjectProtocol?
    private var timeObserver: Any?
    private var loadTask: Task<Void, Never>?
    private var duration: Double = 0

    init(resolver: PreviewResolver = .shared) {
        self.resolver = resolver
    }

    // MARK: - Intent

    func toggle(_ track: Track) {
        guard nowPlaying?.id == track.id, errorMessage == nil else {
            play(track)
            return
        }
        if isPlaying { pause() } else { resume() }
    }

    func play(_ track: Track) {
        teardown()
        nowPlaying = track
        errorMessage = nil
        progress = 0
        isLoading = true

        loadTask = Task { [weak self] in
            await self?.load(track)
        }
    }

    func pause() {
        player?.pause()
        isPlaying = false
    }

    func resume() {
        guard let player else { return }
        activateSession()
        player.play()
        isPlaying = true
    }

    func stop() {
        teardown()
        nowPlaying = nil
        errorMessage = nil
        progress = 0
    }

    // MARK: - Loading

    private func load(_ track: Track) async {
        guard let url = await resolver.previewURL(for: track) else {
            fail("No preview available for this track.", for: track)
            return
        }

        let asset = AVURLAsset(url: url)
        do {
            let (playable, assetDuration) = try await asset.load(.isPlayable, .duration)
            guard playable else {
                fail("This preview can't be played.", for: track)
                return
            }
            let seconds = assetDuration.seconds
            duration = seconds.isFinite && seconds > 0 ? seconds : 0
            begin(with: asset, for: track)
        } catch {
            fail("Couldn't load this preview.", for: track)
        }
    }

    private func begin(with asset: AVURLAsset, for track: Track) {
        // A newer tap may have landed while the asset was loading.
        guard nowPlaying?.id == track.id else { return }

        let item = AVPlayerItem(asset: asset)
        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { _ in
            Task { @MainActor [weak self] in self?.finish() }
        }

        let player = AVPlayer(playerItem: item)
        self.player = player
        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 0.2, preferredTimescale: 600),
            queue: .main
        ) { time in
            Task { @MainActor [weak self] in self?.tick(time) }
        }

        activateSession()
        isLoading = false
        isPlaying = true
        player.play()
    }

    private func fail(_ message: String, for track: Track) {
        guard nowPlaying?.id == track.id else { return }
        isLoading = false
        isPlaying = false
        errorMessage = message
    }

    /// Preview ran out: hold the track in the bar so it can be replayed.
    private func finish() {
        player?.seek(to: .zero)
        isPlaying = false
        progress = 0
    }

    private func tick(_ time: CMTime) {
        guard duration > 0 else { return }
        progress = min(max(time.seconds / duration, 0), 1)
    }

    private func activateSession() {
        // .playback so a preview is still audible with the ringer switch off.
        try? AVAudioSession.sharedInstance().setCategory(.playback)
        try? AVAudioSession.sharedInstance().setActive(true)
    }

    private func teardown() {
        loadTask?.cancel()
        loadTask = nil
        if let timeObserver {
            player?.removeTimeObserver(timeObserver)
        }
        timeObserver = nil
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
        }
        endObserver = nil
        player?.pause()
        player = nil
        isPlaying = false
        isLoading = false
        duration = 0
    }
}
