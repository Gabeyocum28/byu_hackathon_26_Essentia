//
//  APIClient.swift
//  Hackathon
//
//  The only thing that talks to the server. Mirrors contract/contract.md
//  exactly: GET /search, POST /seed, GET /axes, GET /recommend. All responses
//  decode the same uniform `Track`.
//

import Foundation

enum APIError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case status(Int)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid request URL."
        case .invalidResponse: return "The server sent an unexpected response."
        case .status(let code): return "The server returned status \(code)."
        case .decoding: return "The server response could not be read."
        }
    }
}

actor APIClient {
    static let shared = APIClient(baseURL: AppConfig.baseURL)

    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    // MARK: - Contract endpoints

    /// GET /search?q=...
    func search(query: String) async throws -> [Track] {
        try await get("search", query: [URLQueryItem(name: "q", value: query)], as: TracksResponse.self).results
    }

    /// POST /seed { track_id }. Blocking on the server: warm instant, cold
    /// up to ~20s while the embed worker analyzes — hence the long timeout.
    @discardableResult
    func seed(trackID: String) async throws -> SeedResponse {
        try await post("seed", body: ["track_id": trackID], as: SeedResponse.self, timeout: 30)
    }

    /// GET /axes
    func axes() async throws -> [Axis] {
        try await get("axes", as: AxesResponse.self).axes
    }

    /// GET /recommend?track_id=...&axis=...&limit=...
    func recommend(trackID: String, axis: String, limit: Int = 10) async throws -> [Track] {
        try await get("recommend", query: [
            URLQueryItem(name: "track_id", value: trackID),
            URLQueryItem(name: "axis", value: axis),
            URLQueryItem(name: "limit", value: String(limit)),
        ], as: RecommendResponse.self).results
    }

    /// GET /viz/map?track_id=...&axis=...&limit=... — demo/debug endpoint
    /// behind the Insights screen, NOT part of contract/contract.md.
    func vizMap(trackID: String, axis: String, limit: Int = 10,
                correction: Bool? = nil) async throws -> VizMap {
        var query = [
            URLQueryItem(name: "track_id", value: trackID),
            URLQueryItem(name: "axis", value: axis),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        if let correction {
            query.append(URLQueryItem(name: "correction",
                                      value: correction ? "on" : "off"))
        }
        return try await get("viz/map", query: query, as: VizMap.self)
    }

    func vizWalk(from: String, to: String, k: Int = 8) async throws -> VizWalk {
        try await get("viz/walk", query: [
            URLQueryItem(name: "from", value: from),
            URLQueryItem(name: "to", value: to),
            URLQueryItem(name: "k", value: String(k)),
        ], as: VizWalk.self)
    }

    func vizHistogram(trackID: String) async throws -> VizHistogram {
        try await get("viz/histogram", query: [
            URLQueryItem(name: "track_id", value: trackID),
        ], as: VizHistogram.self)
    }

    func vizHubs() async throws -> VizHubs {
        try await get("viz/hubs", as: VizHubs.self)
    }

    // MARK: - Transport

    private func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], as type: T.Type) async throws -> T {
        guard var components = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        return try await send(request, as: type)
    }

    private func post<T: Decodable>(_ path: String, body: [String: String], as type: T.Type, timeout: TimeInterval? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        if let timeout { request.timeoutInterval = timeout }
        return try await send(request, as: type)
    }

    private func send<T: Decodable>(_ request: URLRequest, as type: T.Type) async throws -> T {
        var request = request
        for (field, value) in AppConfig.extraHeaders {
            request.setValue(value, forHTTPHeaderField: field)
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw APIError.status(http.statusCode) }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    // MARK: - Response envelopes

    private struct TracksResponse: Decodable {
        let results: [Track]
    }

    private struct AxesResponse: Decodable {
        let axes: [Axis]
    }

    private struct RecommendResponse: Decodable {
        let seedTrackID: String
        let axis: String
        let results: [Track]

        enum CodingKeys: String, CodingKey {
            case seedTrackID = "seed_track_id"
            case axis
            case results
        }
    }
}

nonisolated struct SeedResponse: Decodable {
    let trackID: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case trackID = "track_id"
        case status
    }
}
