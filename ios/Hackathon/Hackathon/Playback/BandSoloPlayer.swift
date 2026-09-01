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

    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var isAttached = false

    /// Plays `samples` (mono, `sampleRate` Hz) once. Any prior solo playback
    /// is stopped first.
    func play(samples: [Float], sampleRate: Double) {
        stop()
        guard !samples.isEmpty,
              let format = AVAudioFormat(commonFormat: .pcmFormatFloat32,
                                         sampleRate: sampleRate, channels: 1,
                                         interleaved: false),
              let buffer = AVAudioPCMBuffer(pcmFormat: format,
                                            frameCapacity: AVAudioFrameCount(samples.count))
        else { return }

        buffer.frameLength = AVAudioFrameCount(samples.count)
        samples.withUnsafeBufferPointer { src in
            buffer.floatChannelData?[0].update(from: src.baseAddress!, count: samples.count)
        }

        if !isAttached {
            engine.attach(player)
            isAttached = true
        }
        engine.connect(player, to: engine.mainMixerNode, format: format)

        do {
            try engine.start()
        } catch {
            return
        }

        isPlaying = true
        player.scheduleBuffer(buffer, at: nil, options: []) { [weak self] in
            Task { @MainActor [weak self] in
                self?.isPlaying = false
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
