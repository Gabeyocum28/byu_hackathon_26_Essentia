//
//  TourView.swift
//  Hackathon
//
//  T2.1 Grand Tour: every track's 8-d PCA coordinates projected through a
//  slowly rotating orthonormal 2-frame. Clusters that persist under rotation
//  are real; clusters that appear only from one angle are projection
//  artifacts. Frame math lives in GivensTourFrame so it's independently
//  testable of the view.
//

import SwiftUI

/// Chained-Givens-rotation Grand Tour frame in R^8. Deterministic in `t` (each
/// frame is recomputed from scratch, not accumulated), so there is no drift
/// to correct across the animation's lifetime — only within one call, where a
/// defensive re-orthonormalization guards against float error.
struct GivensTourFrame: Equatable {
    static let dimension = 8

    /// All 28 unordered coordinate pairs for dimension 8.
    static let pairs: [(Int, Int)] = {
        var result: [(Int, Int)] = []
        for i in 0..<dimension {
            for j in (i + 1)..<dimension {
                result.append((i, j))
            }
        }
        return result
    }()

    private static let primes: [Double] = [
        2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61,
        67, 71, 73, 79, 83, 89, 97, 101, 103, 107,
    ]

    /// One angular speed per pair, scaled by sqrt of a distinct prime: every
    /// pair's rotation rate is irrational and incommensurate with every
    /// other's, so the frame never falls into a repeating cycle.
    static let speeds: [Double] = primes.prefix(pairs.count).map { 0.05 * $0.squareRoot() }

    /// Orthonormal (e1, e2) at time t: the standard basis (e1=axis0, e2=axis1)
    /// rotated by every pair's Givens rotation G(theta_ij(t)) in sequence.
    static func frame(at t: Double) -> (e1: [Double], e2: [Double]) {
        var e1 = [Double](repeating: 0, count: dimension); e1[0] = 1
        var e2 = [Double](repeating: 0, count: dimension); e2[1] = 1
        for (index, pair) in pairs.enumerated() {
            let theta = speeds[index] * t
            let c = cos(theta), s = sin(theta)
            rotate(&e1, i: pair.0, j: pair.1, cos: c, sin: s)
            rotate(&e2, i: pair.0, j: pair.1, cos: c, sin: s)
        }
        return orthonormalize(e1, e2)
    }

    /// Projects one 8-d row onto (e1, e2): two dot products, zero allocation.
    static func project(_ row: [Float], e1: [Double], e2: [Double]) -> (x: Double, y: Double) {
        var x = 0.0, y = 0.0
        for k in 0..<dimension {
            let value = Double(row[k])
            x += value * e1[k]
            y += value * e2[k]
        }
        return (x, y)
    }

    private static func rotate(_ v: inout [Double], i: Int, j: Int, cos c: Double, sin s: Double) {
        let vi = v[i], vj = v[j]
        v[i] = c * vi - s * vj
        v[j] = s * vi + c * vj
    }

    /// Gram-Schmidt: each individual Givens rotation is exactly orthogonal,
    /// so this is mathematically a no-op, but guards against accumulated
    /// float error across 28 chained rotations.
    private static func orthonormalize(_ e1: [Double], _ e2: [Double]) -> ([Double], [Double]) {
        let n1 = norm(e1)
        let u1 = n1 > 0 ? e1.map { $0 / n1 } : e1
        let projection = zip(u1, e2).reduce(0) { $0 + $1.0 * $1.1 }
        var w2 = zip(e2, u1).map { $0 - projection * $1 }
        let n2 = norm(w2)
        if n2 > 0 { w2 = w2.map { $0 / n2 } }
        return (u1, w2)
    }

    private static func norm(_ v: [Double]) -> Double {
        sqrt(v.reduce(0) { $0 + $1 * $1 })
    }
}

/// Reusable projection scratch space: sized once per tour payload, mutated in
/// place every animation frame so the 60fps draw loop performs no allocation.
private final class TourProjectionBuffer {
    var x: [Double]
    var y: [Double]

    init(count: Int) {
        x = [Double](repeating: 0, count: count)
        y = [Double](repeating: 0, count: count)
    }
}

struct TourView: View {
    let tour: VizTour?
    let errorMessage: String?

    @State private var isPlaying = true
    @State private var pausedElapsed: Double = 0
    @State private var playStartDate: Date = .now
    @State private var buffer: TourProjectionBuffer?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 220)
            } else if let tour {
                canvas(tour)
                caption(tour)
            } else {
                ProgressView("Projecting the grand tour \u{2026}")
                    .tint(.white)
                    .frame(maxWidth: .infinity, minHeight: 220)
            }
        }
        .onAppear { ensureBuffer() }
        .onChange(of: tour?.ids.count) { _, _ in ensureBuffer() }
    }

    private func ensureBuffer() {
        guard let tour, buffer == nil || buffer?.x.count != tour.coords.count else { return }
        buffer = TourProjectionBuffer(count: tour.coords.count)
    }

    private func canvas(_ tour: VizTour) -> some View {
        TimelineView(.animation(paused: !isPlaying)) { context in
            let t = elapsed(at: context.date)
            let frame = GivensTourFrame.frame(at: t)
            Canvas { ctx, size in
                draw(tour: tour, frame: frame, in: ctx, size: size)
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .background(.black, in: .rect(cornerRadius: 12))
        .accessibilityLabel("Grand Tour: rotating 8-dimensional projection of the corpus")
    }

    private func elapsed(at date: Date) -> Double {
        isPlaying ? pausedElapsed + date.timeIntervalSince(playStartDate) : pausedElapsed
    }

    private func draw(tour: VizTour, frame: (e1: [Double], e2: [Double]),
                      in context: GraphicsContext, size: CGSize) {
        guard let buffer, buffer.x.count == tour.coords.count else { return }
        for i in tour.coords.indices {
            let (x, y) = GivensTourFrame.project(tour.coords[i], e1: frame.e1, e2: frame.e2)
            buffer.x[i] = x
            buffer.y[i] = y
        }
        let transform = PointTransform(x: buffer.x, y: buffer.y, size: size)
        for i in buffer.x.indices {
            let p = transform.place(x: buffer.x[i], y: buffer.y[i])
            guard transform.isVisible(p, in: size, margin: 6) else { continue }
            context.fill(
                Path(ellipseIn: CGRect(x: p.x - 1.2, y: p.y - 1.2, width: 2.4, height: 2.4)),
                with: .color(.white.opacity(0.55))
            )
        }
    }

    private func caption(_ tour: VizTour) -> some View {
        HStack(spacing: 10) {
            Button { togglePlay() } label: {
                Image(systemName: isPlaying ? "pause.fill" : "play.fill")
            }
            .buttonStyle(.bordered)
            .accessibilityLabel(isPlaying ? "Pause tour" : "Play tour")

            Text("top-8 PCs hold \(tour.variance.reduce(0, +) * 100, specifier: "%.1f")% of variance")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
        }
    }

    private func togglePlay() {
        if isPlaying {
            pausedElapsed += Date().timeIntervalSince(playStartDate)
        } else {
            playStartDate = Date()
        }
        isPlaying.toggle()
    }
}
