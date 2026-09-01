//
//  BandSoloDSPTests.swift
//  HackathonTests
//
//  T2.5 band-solo: the complex STFT, its raised-cosine mask, and the
//  inverse-STFT overlap-add resynthesis. All pure DSP, no UI/AVFoundation.
//

import Foundation
import Testing
@testable import Hackathon

struct BandSoloDSPTests {
    private let sampleRate = 44_100.0
    private let fftSize = 2048
    private let hop = 1024

    // MARK: - Mask construction

    @Test func maskIsOneInsidePassbandAndZeroFarOutside() {
        let mask = BandSoloMask.raisedCosine(bins: 100, loBin: 20, hiBin: 40, taperBins: 4)
        #expect(mask.count == 100)
        for b in 20...40 { #expect(mask[b] == 1) }
        #expect(mask[0] == 0)
        #expect(mask[99] == 0)
    }

    @Test func maskTapersMonotonicallyOutward() {
        let mask = BandSoloMask.raisedCosine(bins: 100, loBin: 30, hiBin: 30, taperBins: 5)
        // Above the passband: 31...35 should strictly decrease toward 0.
        for b in 31..<35 {
            #expect(mask[b] > mask[b + 1])
        }
        #expect(mask[36] == 0)
        #expect(mask[24] == 0)
    }

    @Test func zeroTaperIsABrickWall() {
        let mask = BandSoloMask.raisedCosine(bins: 20, loBin: 5, hiBin: 8, taperBins: 0)
        #expect(mask[4] == 0)
        #expect(mask[5] == 1)
        #expect(mask[8] == 1)
        #expect(mask[9] == 0)
    }

    // MARK: - COLA sanity: full-range mask reconstructs the original

    @Test func fullRangeMaskReconstructsOriginalOnInteriorSegment() throws {
        let n = Int(sampleRate) // 1s
        let samples = (0..<n).map { i -> Float in
            Float(0.6 * sin(2 * .pi * 440 * Double(i) / sampleRate)
                  + 0.3 * sin(2 * .pi * 1200 * Double(i) / sampleRate))
        }
        let stft = try #require(STFTComplex(samples: samples, sampleRate: sampleRate,
                                            fftSize: fftSize, hop: hop))
        let mask = BandSoloMask.raisedCosine(bins: stft.bins, loBin: 0, hiBin: stft.bins - 1,
                                             taperBins: 0)
        let recon = stft.resynthesize(mask: mask)
        #expect(recon.count == stft.outputLength)

        // Skip one window's worth of samples at each edge (fade-in/out from
        // partial window coverage — expected, not an error).
        let start = fftSize
        let end = recon.count - fftSize
        try #require(end > start)

        var errSq: Double = 0
        var refSq: Double = 0
        for i in start..<end {
            let diff = Double(recon[i] - samples[i])
            errSq += diff * diff
            refSq += Double(samples[i]) * Double(samples[i])
        }
        let relError = sqrt(errSq / refSq)
        #expect(relError < 0.02)
    }

    // MARK: - Band-solo isolates the in-band tone

    @Test func soloingABandKeepsInBandToneAndAttenuatesOutOfBandTone() throws {
        let n = Int(sampleRate) // 1s
        let freqIn = 300.0
        let freqOut = 6_000.0
        let mixture = (0..<n).map { i -> Float in
            Float(sin(2 * .pi * freqIn * Double(i) / sampleRate)
                  + sin(2 * .pi * freqOut * Double(i) / sampleRate))
        }

        let stft = try #require(STFTComplex(samples: mixture, sampleRate: sampleRate,
                                            fftSize: fftSize, hop: hop))
        let loBin = stft.bin(forHz: 200)
        let hiBin = stft.bin(forHz: 400)
        let mask = BandSoloMask.raisedCosine(bins: stft.bins, loBin: loBin, hiBin: hiBin,
                                             taperBins: 4)
        let recon = stft.resynthesize(mask: mask)

        let start = fftSize
        let end = recon.count - fftSize
        try #require(end > start)
        let interior = recon[start..<end]

        let inBandMagnitude = Self.toneMagnitude(interior, freq: freqIn, sampleRate: sampleRate,
                                                  startIndex: start)
        let outOfBandMagnitude = Self.toneMagnitude(interior, freq: freqOut, sampleRate: sampleRate,
                                                     startIndex: start)

        // The 300 Hz tone (unit amplitude sine) should survive close to its
        // original amplitude...
        #expect(inBandMagnitude > 0.7)
        // ...while the 6 kHz tone should be attenuated by a large factor.
        #expect(outOfBandMagnitude < inBandMagnitude / 10)
    }

    /// Estimates the amplitude of a `freq` Hz sinusoid present in `signal`
    /// via quadrature (I/Q) correlation — a Goertzel-style single-frequency
    /// "RMS at freq" probe that doesn't care about the signal's phase.
    private static func toneMagnitude(_ signal: ArraySlice<Float>, freq: Double,
                                      sampleRate: Double, startIndex: Int) -> Float {
        var sumI = 0.0
        var sumQ = 0.0
        for (offset, x) in signal.enumerated() {
            let t = Double(startIndex + offset) / sampleRate
            sumI += Double(x) * cos(2 * .pi * freq * t)
            sumQ += Double(x) * sin(2 * .pi * freq * t)
        }
        let count = Double(signal.count)
        return Float(2 * sqrt(sumI * sumI + sumQ * sumQ) / count)
    }
}
