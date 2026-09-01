//
//  BandSoloDSP.swift
//  Hackathon
//
//  T2.5 band-solo: the pure DSP half. A parallel complex STFT (kept separate
//  from MelSpectrogram's power-only pass — that one throws phase away on
//  purpose) that retains magnitude AND phase per bin, a raised-cosine band
//  mask (a brick wall rings — Gibbs), and inverse-STFT overlap-add
//  resynthesis. No UI, no AVFoundation: everything here is Float arrays in,
//  Float arrays out, so it is directly unit-testable.
//
//  FFT convention: this reuses the exact vDSP.FFT<DSPSplitComplex> "packed
//  real FFT via half-size complex FFT" trick MelSpectrogram uses (ctoz ->
//  forward -> half=fftSize/2 complex bins, bin 0's imaginary slot smuggles
//  the real-valued Nyquist term). Round-tripping forward+inverse through
//  that FFT scales the signal by exactly 2*fftSize (verified empirically);
//  resynthesize() divides it back out. The Nyquist term is dropped (set to
//  0), same as MelSpectrogram — inaudible for a 30s preview's content.
//
//  COLA note: Hann + 50% overlap (hop = fftSize/2) sums to a *constant 1.0*
//  in the interior with a single analysis-only window (no separate
//  synthesis window needed) — verified numerically against
//  MelSpectrogram's own `.hanningDenormalized` window. So overlap-add of
//  the (masked, phase-preserved) inverse-FFT frames reconstructs the
//  interior of the signal directly; only the first/last half-window of
//  samples fade in/out, which is a feature here (click-free start/stop).
//

import Accelerate
import Foundation

// vDSP.FFT<DSPSplitComplex> isn't declared Sendable, but it's an immutable
// computation kernel handle (an FFTSetup wrapper) safe to hand across
// isolation domains for pure, read-only use — which is all this does: build
// once off the main actor, cache, then mask+inverse-FFT (also off the main
// actor) on demand.
nonisolated struct STFTComplex: @unchecked Sendable {
    let fftSize: Int
    let hop: Int
    let sampleRate: Double
    /// Number of usable frequency bins (fftSize/2); bin b ~= b * sampleRate/fftSize Hz.
    let bins: Int
    let frameCount: Int
    /// Length of the buffer resynthesize(mask:) will return.
    let outputLength: Int

    /// Per frame, `bins` real/imaginary values (phase preserved).
    private let real: [[Float]]
    private let imag: [[Float]]
    private let window: [Float]
    private let fft: vDSP.FFT<DSPSplitComplex>

    init?(samples: [Float], sampleRate: Double, fftSize: Int = 2048, hop: Int = 1024) {
        guard samples.count >= fftSize, fftSize > 0, hop > 0 else { return nil }
        self.fftSize = fftSize
        self.hop = hop
        self.sampleRate = sampleRate
        let bins = fftSize / 2
        self.bins = bins
        let frameCount = (samples.count - fftSize) / hop + 1
        self.frameCount = frameCount
        self.outputLength = (frameCount - 1) * hop + fftSize

        let window = vDSP.window(ofType: Float.self, usingSequence: .hanningDenormalized,
                                 count: fftSize, isHalfWindow: false)
        self.window = window
        let log2n = vDSP_Length(log2(Double(fftSize)))
        guard let fft = vDSP.FFT(log2n: log2n, radix: .radix2, ofType: DSPSplitComplex.self) else {
            return nil
        }
        self.fft = fft

        var allReal: [[Float]] = []
        var allImag: [[Float]] = []
        allReal.reserveCapacity(frameCount)
        allImag.reserveCapacity(frameCount)

        var windowed = [Float](repeating: 0, count: fftSize)
        var r = [Float](repeating: 0, count: bins)
        var i = [Float](repeating: 0, count: bins)
        var outR = [Float](repeating: 0, count: bins)
        var outI = [Float](repeating: 0, count: bins)

        for frame in 0..<frameCount {
            let startIdx = frame * hop
            samples.withUnsafeBufferPointer { buf in
                vDSP_vmul(buf.baseAddress! + startIdx, 1, window, 1,
                          &windowed, 1, vDSP_Length(fftSize))
            }
            r.withUnsafeMutableBufferPointer { rp in
                i.withUnsafeMutableBufferPointer { ip in
                    var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                    windowed.withUnsafeBufferPointer { wp in
                        wp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: bins) {
                            vDSP_ctoz($0, 2, &split, 1, vDSP_Length(bins))
                        }
                    }
                    outR.withUnsafeMutableBufferPointer { orp in
                        outI.withUnsafeMutableBufferPointer { oip in
                            var out = DSPSplitComplex(realp: orp.baseAddress!, imagp: oip.baseAddress!)
                            fft.forward(input: split, output: &out)
                            // Drop the smuggled Nyquist term (see header note).
                            oip.baseAddress![0] = 0
                        }
                    }
                }
            }
            allReal.append(outR)
            allImag.append(outI)
        }
        self.real = allReal
        self.imag = allImag
    }

    /// The FFT bin nearest `hz`, clamped to a valid index.
    func bin(forHz hz: Double) -> Int {
        let binHz = sampleRate / Double(fftSize)
        return max(0, min(bins - 1, Int((hz / binHz).rounded())))
    }

    /// Applies a per-bin gain mask (length `bins`, values typically 0...1,
    /// same mask for every frame) to the retained magnitude+phase spectrum,
    /// inverse-FFTs each frame, and overlap-adds back into a mono buffer.
    func resynthesize(mask: [Float]) -> [Float] {
        guard frameCount > 0, mask.count == bins else { return [] }
        var output = [Float](repeating: 0, count: outputLength)
        let scale: Float = 1 / Float(2 * fftSize)

        var r = [Float](repeating: 0, count: bins)
        var i = [Float](repeating: 0, count: bins)
        var backR = [Float](repeating: 0, count: bins)
        var backI = [Float](repeating: 0, count: bins)
        var frame = [Float](repeating: 0, count: fftSize)

        for f in 0..<frameCount {
            vDSP_vmul(real[f], 1, mask, 1, &r, 1, vDSP_Length(bins))
            vDSP_vmul(imag[f], 1, mask, 1, &i, 1, vDSP_Length(bins))

            r.withUnsafeMutableBufferPointer { rp in
                i.withUnsafeMutableBufferPointer { ip in
                    var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                    backR.withUnsafeMutableBufferPointer { brp in
                        backI.withUnsafeMutableBufferPointer { bip in
                            var backSplit = DSPSplitComplex(realp: brp.baseAddress!, imagp: bip.baseAddress!)
                            fft.inverse(input: split, output: &backSplit)
                            frame.withUnsafeMutableBufferPointer { fbuf in
                                fbuf.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: bins) { dst in
                                    vDSP_ztoc(&backSplit, 1, dst, 2, vDSP_Length(bins))
                                }
                            }
                            var s = scale
                            vDSP_vsmul(frame, 1, &s, &frame, 1, vDSP_Length(fftSize))
                        }
                    }
                }
            }

            let start = f * hop
            output.withUnsafeMutableBufferPointer { outBuf in
                frame.withUnsafeBufferPointer { frameBuf in
                    vDSP_vadd(outBuf.baseAddress! + start, 1, frameBuf.baseAddress!, 1,
                              outBuf.baseAddress! + start, 1, vDSP_Length(fftSize))
                }
            }
        }
        return output
    }
}

/// Pure mask-construction helpers, split out from STFTComplex so they're
/// trivially testable on their own.
nonisolated enum BandSoloMask {
    /// A gain mask of length `bins`: 1.0 across [loBin, hiBin], tapered to 0
    /// over `taperBins` bins on each side with a raised cosine (a brick-wall
    /// cutoff rings — Gibbs).
    static func raisedCosine(bins: Int, loBin: Int, hiBin: Int, taperBins: Int) -> [Float] {
        guard bins > 0 else { return [] }
        let lo = max(0, min(loBin, bins - 1))
        let hi = max(lo, min(hiBin, bins - 1))
        var mask = [Float](repeating: 0, count: bins)
        for b in lo...hi { mask[b] = 1 }

        let taper = max(0, taperBins)
        guard taper > 0 else { return mask }
        for t in 1...taper {
            // Raised-cosine ramp: ~1 just outside the passband, ~0 by `taper`
            // bins out.
            let gain = Float(0.5 * (1 + cos(.pi * Double(t) / Double(taper + 1))))
            let below = lo - t
            if below >= 0 { mask[below] = max(mask[below], gain) }
            let above = hi + t
            if above < bins { mask[above] = max(mask[above], gain) }
        }
        return mask
    }
}
