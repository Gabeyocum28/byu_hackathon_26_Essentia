//
//  SelfSimilarityMatrixTests.swift
//  HackathonTests
//
//  T2.3 self-similarity matrix: pure pooling + cosine Gram math, no UI.
//

import Foundation
import Testing
@testable import Hackathon

struct SelfSimilarityMatrixTests {

    @Test func poolsDownToAtMostMaxColumns() {
        // 500 frames of 8 bands each, pooled to <=64 columns.
        let frames = (0..<500).map { i in
            (0..<8).map { Float($0 + i) }
        }
        let matrix = SelfSimilarityMatrix(frames: frames, maxColumns: 64)
        #expect(matrix.columns == 64)
        #expect(matrix.bands == 8)
        #expect(matrix.values.count == 64 * 64)
    }

    @Test func neverUpsamplesFewerFramesThanTarget() {
        let frames = (0..<10).map { i in [Float(i), Float(i) * 2] }
        let matrix = SelfSimilarityMatrix(frames: frames, maxColumns: 256)
        #expect(matrix.columns == 10)
    }

    @Test func emptyFramesYieldEmptyMatrix() {
        let matrix = SelfSimilarityMatrix(frames: [])
        #expect(matrix.columns == 0)
        #expect(matrix.values.isEmpty)
    }

    @Test func gramMatrixIsSymmetric() {
        let frames = (0..<40).map { i in
            (0..<12).map { b in Float(sin(Double(i) * 0.3 + Double(b))) }
        }
        let matrix = SelfSimilarityMatrix(frames: frames, maxColumns: 40)
        for r in 0..<matrix.columns {
            for c in 0..<matrix.columns {
                #expect(abs(matrix[r, c] - matrix[c, r]) < 1e-4)
            }
        }
    }

    @Test func diagonalIsApproximatelyOneForNonzeroFrames() {
        let frames = (0..<30).map { i in
            (0..<16).map { b in Float((i + 1) * (b + 1)) }
        }
        let matrix = SelfSimilarityMatrix(frames: frames, maxColumns: 30)
        for i in 0..<matrix.columns {
            #expect(abs(matrix[i, i] - 1) < 1e-4)
        }
    }

    @Test func similarityRangeStaysWithinMinusOneToOne() {
        let frames = (0..<20).map { i in
            (0..<10).map { b in Float.random(in: -5...5) * Float(i - b) }
        }
        let matrix = SelfSimilarityMatrix(frames: frames, maxColumns: 20)
        for v in matrix.values {
            #expect(v >= -1.001 && v <= 1.001)
        }
    }
}
