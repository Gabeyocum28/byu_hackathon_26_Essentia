//
//  SelfSimilarityMatrix.swift
//  Hackathon
//
//  T2.3 self-similarity ("recurrence") matrix: average-pool the mel frames
//  down to <=256 time columns, L2-normalize each column across bands, then
//  take the cosine Gram matrix S^T . S. Repeating structure (choruses,
//  refrains — Foote 1999) shows up as bright off-diagonal blocks.
//

import Accelerate
import CoreGraphics
import Foundation

nonisolated struct SelfSimilarityMatrix {
    let columns: Int
    let bands: Int
    /// Row-major cosine similarities, columns x columns, values in [-1, 1].
    let values: [Float]

    static let maxColumns = 256

    /// `frames`: one array of `bands` dB values per STFT hop, as produced by
    /// `MelSpectrogram.compute`.
    init(frames: [[Float]], maxColumns: Int = SelfSimilarityMatrix.maxColumns) {
        guard let bandCount = frames.first?.count, !frames.isEmpty else {
            self.columns = 0
            self.bands = 0
            self.values = []
            return
        }
        self.bands = bandCount

        // 1. Average-pool frames in time down to <=maxColumns columns.
        let pooled = Self.pool(frames: frames, bands: bandCount, target: maxColumns)
        let columns = pooled.count
        self.columns = columns

        // 2. L2-normalize each column (a "column" is one pooled frame of
        // `bands` values) so the Gram matrix is a cosine similarity.
        var normalized = pooled
        for i in 0..<columns {
            var norm: Float = 0
            vDSP_svesq(normalized[i], 1, &norm, vDSP_Length(bandCount))
            let mag = sqrt(norm)
            guard mag > 0 else { continue }
            var scale = 1 / mag
            vDSP_vsmul(normalized[i], 1, &scale, &normalized[i], 1, vDSP_Length(bandCount))
        }

        // 3. Gram matrix: values[r*columns+c] = dot(col_r, col_c).
        var gram = [Float](repeating: 0, count: columns * columns)
        for r in 0..<columns {
            for c in r..<columns {
                var dot: Float = 0
                vDSP_dotpr(normalized[r], 1, normalized[c], 1, &dot, vDSP_Length(bandCount))
                gram[r * columns + c] = dot
                gram[c * columns + r] = dot
            }
        }
        self.values = gram
    }

    subscript(row: Int, col: Int) -> Float {
        values[row * columns + col]
    }

    /// Average-pool `frames` (each `bands` long) down to at most `target`
    /// columns in time. Never upsamples: fewer frames than `target` pass
    /// through untouched.
    private static func pool(frames: [[Float]], bands: Int, target: Int) -> [[Float]] {
        let total = frames.count
        guard total > target else { return frames }

        var pooled: [[Float]] = []
        pooled.reserveCapacity(target)
        for col in 0..<target {
            let start = total * col / target
            let end = max(start + 1, total * (col + 1) / target)
            var sum = [Float](repeating: 0, count: bands)
            for f in start..<end {
                vDSP_vadd(sum, 1, frames[f], 1, &sum, 1, vDSP_Length(bands))
            }
            var count = Float(end - start)
            vDSP_vsdiv(sum, 1, &count, &sum, 1, vDSP_Length(bands))
            pooled.append(sum)
        }
        return pooled
    }

    // MARK: - Rendering

    /// Renders the matrix as a square heatmap image using `colormap` to map
    /// [-1, 1] similarity to RGB. Row 0 of the image is time column 0 (top).
    func image(colormap: (CGFloat) -> (CGFloat, CGFloat, CGFloat)) -> CGImage? {
        guard columns > 0 else { return nil }
        var pixels = [UInt8](repeating: 0, count: columns * columns * 4)
        for row in 0..<columns {
            for col in 0..<columns {
                let similarity = self[row, col]
                let t = CGFloat((similarity + 1) / 2)
                let (r, g, b) = colormap(max(0, min(1, t)))
                let idx = (row * columns + col) * 4
                pixels[idx] = UInt8(r * 255)
                pixels[idx + 1] = UInt8(g * 255)
                pixels[idx + 2] = UInt8(b * 255)
                pixels[idx + 3] = 255
            }
        }
        let space = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        guard let context = CGContext(
            data: &pixels, width: columns, height: columns, bitsPerComponent: 8,
            bytesPerRow: columns * 4, space: space, bitmapInfo: info
        ) else { return nil }
        return context.makeImage()
    }
}
