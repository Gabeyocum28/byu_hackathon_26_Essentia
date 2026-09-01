//
//  MelSpectrogram.swift
//  Hackathon
//
//  STFT + triangular mel filterbank, all vDSP. Computed once per downloaded
//  preview and rendered as a static heatmap with a moving playhead — AVPlayer
//  offers no clean audio tap, and a precomputed image can't glitch on stage.
//

import Accelerate
import Foundation

nonisolated struct MelSpectrogram {
    /// Silence clamps to exactly this dB value.
    static let dbFloor: Float = -80

    let bands: Int
    let sampleRate: Double
    let fftSize: Int
    let hop: Int

    private let window: [Float]
    private let fft: vDSP.FFT<DSPSplitComplex>
    /// Per band: first FFT bin plus the triangular weights from there up.
    private let filters: [(start: Int, weights: [Float])]
    private let melCenters: [Double]
    /// bands+2 Hz edges of the equal-mel triangular filterbank (band b's
    /// triangle spans edges[b]...edges[b+2]) — exposed so band-solo (T2.5)
    /// can map a selected band range to an Hz range using the exact same
    /// slicing the rendered spectrogram uses.
    let bandEdgesHz: [Double]

    init(bands: Int, sampleRate: Double, minHz: Double = 20,
         fftSize: Int = 1024, hop: Int = 512) {
        self.bands = bands
        self.sampleRate = sampleRate
        self.fftSize = fftSize
        self.hop = hop
        self.window = vDSP.window(ofType: Float.self, usingSequence: .hanningDenormalized,
                                  count: fftSize, isHalfWindow: false)

        let log2n = vDSP_Length(log2(Double(fftSize)))
        self.fft = vDSP.FFT(log2n: log2n, radix: .radix2, ofType: DSPSplitComplex.self)!

        let maxHz = sampleRate / 2
        let melMin = Self.mel(fromHz: minHz)
        let melMax = Self.mel(fromHz: maxHz)
        let edges = (0..<(bands + 2)).map {
            Self.hz(fromMel: melMin + (melMax - melMin) * Double($0) / Double(bands + 1))
        }
        self.melCenters = edges[1...bands].map(Self.mel(fromHz:))
        self.bandEdgesHz = edges

        let binHz = sampleRate / Double(fftSize)
        let nBins = fftSize / 2
        self.filters = (0..<bands).map { band in
            let lo = edges[band], mid = edges[band + 1], hi = edges[band + 2]
            let start = max(Int(lo / binHz) + 1, 0)
            let end = min(Int(hi / binHz), nBins - 1)
            guard start <= end else { return (start: 0, weights: [0]) }
            let weights = (start...end).map { bin -> Float in
                let hz = Double(bin) * binHz
                let w = hz <= mid ? (hz - lo) / (mid - lo) : (hi - hz) / (hi - mid)
                return Float(max(w, 0))
            }
            return (start: start, weights: weights)
        }
    }

    // MARK: - Mel scale

    nonisolated static func mel(fromHz hz: Double) -> Double {
        2595 * log10(1 + hz / 700)
    }

    nonisolated static func hz(fromMel mel: Double) -> Double {
        700 * (pow(10, mel / 2595) - 1)
    }

    /// The band whose center is nearest this frequency on the mel scale.
    func bandIndex(forHz hz: Double) -> Int {
        let target = Self.mel(fromHz: hz)
        return melCenters.indices.min {
            abs(melCenters[$0] - target) < abs(melCenters[$1] - target)
        } ?? 0
    }

    /// Hz span covered by bands `range` (inclusive), using the same
    /// triangular filter edges the filterbank itself was built from.
    func hzRange(forBands range: ClosedRange<Int>) -> (lo: Double, hi: Double) {
        let lo = bandEdgesHz[max(0, min(range.lowerBound, bands - 1))]
        let hi = bandEdgesHz[max(0, min(range.upperBound, bands - 1)) + 2]
        return (lo, hi)
    }

    // MARK: - Spectrogram

    /// Frames of `bands` dB values in [dbFloor, ...], hop-strided over samples.
    func compute(samples: [Float]) -> [[Float]] {
        guard samples.count >= fftSize else { return [] }
        let half = fftSize / 2
        let frameCount = (samples.count - fftSize) / hop + 1

        var windowed = [Float](repeating: 0, count: fftSize)
        var real = [Float](repeating: 0, count: half)
        var imag = [Float](repeating: 0, count: half)
        var outReal = [Float](repeating: 0, count: half)
        var outImag = [Float](repeating: 0, count: half)
        var power = [Float](repeating: 0, count: half)

        var frames: [[Float]] = []
        frames.reserveCapacity(frameCount)

        for frame in 0..<frameCount {
            let startIdx = frame * hop
            samples.withUnsafeBufferPointer { buf in
                vDSP_vmul(buf.baseAddress! + startIdx, 1, window, 1,
                          &windowed, 1, vDSP_Length(fftSize))
            }
            real.withUnsafeMutableBufferPointer { rp in
                imag.withUnsafeMutableBufferPointer { ip in
                    var split = DSPSplitComplex(realp: rp.baseAddress!,
                                                imagp: ip.baseAddress!)
                    windowed.withUnsafeBufferPointer { wp in
                        wp.baseAddress!.withMemoryRebound(
                            to: DSPComplex.self, capacity: half
                        ) {
                            vDSP_ctoz($0, 2, &split, 1, vDSP_Length(half))
                        }
                    }
                    outReal.withUnsafeMutableBufferPointer { orp in
                        outImag.withUnsafeMutableBufferPointer { oip in
                            var out = DSPSplitComplex(realp: orp.baseAddress!,
                                                      imagp: oip.baseAddress!)
                            fft.forward(input: split, output: &out)
                            // Packed format smuggles Nyquist into imag[0];
                            // drop it so bin 0 is pure DC.
                            oip.baseAddress![0] = 0
                            vDSP_zvmags(&out, 1, &power, 1, vDSP_Length(half))
                        }
                    }
                }
            }

            var melFrame = [Float](repeating: 0, count: bands)
            for (band, filter) in filters.enumerated() {
                var energy: Float = 0
                power.withUnsafeBufferPointer { buf in
                    vDSP_dotpr(buf.baseAddress! + filter.start, 1,
                               filter.weights, 1, &energy,
                               vDSP_Length(filter.weights.count))
                }
                melFrame[band] = max(10 * log10(max(energy, 1e-10)), Self.dbFloor)
            }
            frames.append(melFrame)
        }
        return frames
    }
}
