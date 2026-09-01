//
//  GivensTourFrameTests.swift
//  HackathonTests
//
//  Pure math tests for the Grand Tour's rotating frame: orthonormality must
//  hold at any time t, and the frame must be deterministic given t (no
//  incremental state to drift).
//

import Foundation
import Testing
@testable import Hackathon

struct GivensTourFrameTests {
    private func dot(_ a: [Double], _ b: [Double]) -> Double {
        zip(a, b).reduce(0) { $0 + $1.0 * $1.1 }
    }

    private func norm(_ v: [Double]) -> Double {
        sqrt(dot(v, v))
    }

    @Test func frameStaysOrthonormalAcrossTime() {
        for t in stride(from: 0.0, through: 40.0, by: 3.7) {
            let (e1, e2) = GivensTourFrame.frame(at: t)
            #expect(e1.count == 8)
            #expect(e2.count == 8)
            #expect(abs(norm(e1) - 1) < 1e-9)
            #expect(abs(norm(e2) - 1) < 1e-9)
            #expect(abs(dot(e1, e2)) < 1e-9)
        }
    }

    @Test func frameIsDeterministicAtAFixedTime() {
        let (e1a, e2a) = GivensTourFrame.frame(at: 12.34)
        let (e1b, e2b) = GivensTourFrame.frame(at: 12.34)
        #expect(e1a == e1b)
        #expect(e2a == e2b)
    }

    @Test func frameAtZeroIsTheStandardBasis() {
        let (e1, e2) = GivensTourFrame.frame(at: 0)
        #expect(e1[0] == 1)
        #expect(e2[1] == 1)
        for k in 1..<8 { #expect(abs(e1[k]) < 1e-12) }
    }

    @Test func projectionMatchesDotProductAgainstTheFrame() {
        let (e1, e2) = GivensTourFrame.frame(at: 5)
        let row: [Float] = [1, 0, 0, 0, 0, 0, 0, 0]
        let (x, y) = GivensTourFrame.project(row, e1: e1, e2: e2)
        #expect(abs(x - e1[0]) < 1e-9)
        #expect(abs(y - e2[0]) < 1e-9)
    }
}
