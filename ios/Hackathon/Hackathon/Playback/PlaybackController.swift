//
//  PlaybackController.swift
//  Hackathon
//
//  Owns a single AVPlayer for 30-second preview playback. Only one preview
//  plays at a time; starting a new one stops the current.
//

import AVFoundation
import Observation

@MainActor
@Observable
final class PlaybackController {
    /// The id of the track currently playing, or nil if stopped.
    private(set) var nowPlayingID: String?

    private var player: AVPlayer?
    private var endObserver: NSObjectProtocol?

    func toggle(_ track: Track) {
        if nowPlayingID == track.id {
            stop()
        } else {
            play(track)
        }
    }

    func play(_ track: Track) {
        guard let url = track.previewURL else { return }
        stop()

        try? AVAudioSession.sharedInstance().setCategory(.playback)
        try? AVAudioSession.sharedInstance().setActive(true)

        let item = AVPlayerItem(url: url)
        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { _ in
            Task { @MainActor [weak self] in self?.stop() }
        }

        let player = AVPlayer(playerItem: item)
        self.player = player
        nowPlayingID = track.id
        player.play()
    }

    func stop() {
        player?.pause()
        player = nil
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
        }
        endObserver = nil
        nowPlayingID = nil
    }
}
