//
//  BandSoloPlayer.swift
//  Hackathon
//
//  Self-contained player for T2.5 band-solo: plays a resynthesized mono
//  Float buffer through its own AVAudioEngine + AVAudioPlayerNode, entirely
//  separate from the shared preview PlaybackController (which owns an
//  AVPlayer, not an engine graph). It does not touch AVAudioSession beyond
//  what PlaybackController already sets up (.playback, active) — the app
//  only ever needs one category active at a time.
//

import AVFoundation
import Observation

@MainActor
@Observable
final class BandSoloPlayer {
    private(set) var isPlaying = false
    /// Set when starting playback failed (e.g. the engine couldn't start);
    /// cleared on the next attempt. Surfaced so a failed solo shows
    /// something instead of silently doing nothing.
    private(set) var errorMessage: String?

    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var isAttached = false

    /// Plays `samples` (mono, `sampleRate` Hz) once. Any prior solo playback
    /// is stopped first.
    func play(samples: [Float], sampleRate: Double) {
        stop()
        errorMessage = nil
        guard !samples.isEmpty,
              let format = AVAudioFormat(commonFormat: .pcmFormatFloat32,
                                         sampleRate: sampleRate, channels: 1,
                                         interleaved: false),
              let buffer = AVAudioPCMBuffer(pcmFormat: format,
                                            frameCapacity: AVAudioFrameCount(samples.count))
        else {
            errorMessage = "Couldn't prepare this band for playback."
            return
        }

        buffer.frameLength = AVAudioFrameCount(samples.count)
        samples.withUnsafeBufferPointer { src in
            buffer.floatChannelData?[0].update(from: src.baseAddress!, count: samples.count)
        }

        // The shared preview only activates AVAudioSession once the user
        // has pressed play on it at least once (PlaybackController.
        // activateSession(), called from resume()/begin(with:for:)). A
        // solo can be the very first audio the app plays, so activate here
        // too — engine.start() otherwise can throw silently.
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            errorMessage = "Couldn't activate audio for playback."
            return
        }

        if !isAttached {
            engine.attach(player)
            isAttached = true
        }
        engine.connect(player, to: engine.mainMixerNode, format: format)

        do {
            try engine.start()
        } catch {
            errorMessage = "Couldn't start audio playback."
            return
        }

        isPlaying = true
        player.scheduleBuffer(buffer, at: nil, options: []) { [weak self] in
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.isPlaying = false
                // Buffer played to completion naturally (not a manual
                // stop()) — release the engine instead of leaving it idle.
                if self.engine.isRunning { self.engine.stop() }
            }
        }
        player.play()
    }

    func stop() {
        player.stop()
        if engine.isRunning { engine.stop() }
        isPlaying = false
    }
}
