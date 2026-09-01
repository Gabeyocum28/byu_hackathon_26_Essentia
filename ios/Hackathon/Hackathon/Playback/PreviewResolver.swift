//
//  PreviewResolver.swift
//  Hackathon
//
//  Deezer signs its preview URLs with roughly a 15-minute expiry, so the
//  `preview_url` that arrives on a Track is usually dead by the time anyone
//  taps play — the CDN answers 403 and AVPlayer just goes quiet. Resolve a
//  fresh URL by track id at tap time instead, and keep the stored one only as
//  a last resort.
//

import Foundation

actor PreviewResolver {
    static let shared = PreviewResolver()

    /// Comfortably inside Deezer's signature lifetime.
    private static let ttl: TimeInterval = 10 * 60
    private static let trackEndpoint = URL(string: "https://api.deezer.com/track/")!

    private let session: URLSession
    private var cache: [String: (url: URL, fetchedAt: Date)] = [:]

    init(session: URLSession = .shared) {
        self.session = session
    }

    /// A playable URL for `track`, freshly signed when Deezer is reachable.
    func previewURL(for track: Track) async -> URL? {
        if let hit = cache[track.trackID], Date().timeIntervalSince(hit.fetchedAt) < Self.ttl {
            return hit.url
        }
        if let fresh = try? await fetch(trackID: track.trackID) {
            cache[track.trackID] = (fresh, Date())
            return fresh
        }
        return track.previewURL
    }

    private func fetch(trackID: String) async throws -> URL {
        struct Payload: Decodable {
            let preview: String?
        }

        let (data, response) = try await session.data(
            from: Self.trackEndpoint.appendingPathComponent(trackID)
        )
        guard let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode) else {
            throw APIError.invalidResponse
        }
        guard let raw = try JSONDecoder().decode(Payload.self, from: data).preview,
              !raw.isEmpty,
              let url = URL(string: raw) else {
            throw APIError.invalidResponse
        }
        return url
    }
}
