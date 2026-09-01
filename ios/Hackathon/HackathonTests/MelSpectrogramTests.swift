//
//  MelSpectrogramTests.swift
//  HackathonTests
//
//  The mel math behind the Insights spectrogram: hz<->mel conversion and the
//  STFT + mel binning pass. A pure sine must light up exactly the band that
//  contains its frequency, silence must sit at the dB floor.
//

import Foundation
import Testing
@testable import Hackathon

struct MelSpectrogramTests {

    @Test func hzMelRoundTrip() {
        for hz in [50.0, 440.0, 1000.0, 8000.0] {
            let back = MelSpectrogram.hz(fromMel: MelSpectrogram.mel(fromHz: hz))
            #expect(abs(back - hz) < 0.01)
        }
    }

    @Test func melIsMonotonic() {
        #expect(MelSpectrogram.mel(fromHz: 200) < MelSpectrogram.mel(fromHz: 400))
        #expect(MelSpectrogram.mel(fromHz: 400) < MelSpectrogram.mel(fromHz: 4000))
    }

    @Test func sineConcentratesInItsMelBand() {
        let sampleRate = 16_000.0
        let freq = 440.0
        let samples = (0..<16_000).map {
            Float(sin(2.0 * .pi * freq * Double($0) / sampleRate))
        }
        let spec = MelSpectrogram(bands: 64, sampleRate: sampleRate)
        let frames = spec.compute(samples: samples)

        #expect(frames.count > 10)
        #expect(frames.allSatisfy { $0.count == 64 })

        // The band whose range contains 440 Hz must be the loudest one.
        let expected = spec.bandIndex(forHz: freq)
        for frame in frames.dropFirst().dropLast() {
            let loudest = frame.indices.max { frame[$0] < frame[$1] }!
            #expect(abs(loudest - expected) <= 1)
        }
    }

    @Test func silenceSitsAtTheFloor() {
        let spec = MelSpectrogram(bands: 64, sampleRate: 16_000)
        let frames = spec.compute(samples: [Float](repeating: 0, count: 8_000))
        #expect(!frames.isEmpty)
        for frame in frames {
            #expect(frame.allSatisfy { $0 <= MelSpectrogram.dbFloor + 0.001 })
        }
    }

    @Test func tooFewSamplesYieldsNoFrames() {
        let spec = MelSpectrogram(bands: 64, sampleRate: 16_000)
        #expect(spec.compute(samples: [Float](repeating: 0, count: 100)).isEmpty)
    }
}
