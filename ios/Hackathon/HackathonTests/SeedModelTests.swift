//
//  SeedModelTests.swift
//  HackathonTests
//
//  SeedModel maps the /seed status to a view state: "ready" shows axis
//  buttons, anything else is the unanalyzed error state.
//

import Foundation
import Testing
@testable import Hackathon

/// Isolated from `MockURLProtocol` (used by `APIClientTests`) so this suite
/// can't race that suite's static handler/lastRequest when suites run
/// concurrently — `.serialized` only serializes within a single suite.
final class SeedMockURLProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) -> (Int, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = SeedMockURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        let (status, data) = handler(request)
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

@Suite(.serialized)
struct SeedModelTests {

    @MainActor
    private func makeModel(seedStatus: String) -> SeedModel {
        SeedMockURLProtocol.handler = { request in
            if request.url!.path.hasSuffix("/seed") {
                return (200, Data(#"{ "track_id": "1", "status": "\#(seedStatus)" }"#.utf8))
            }
            return (200, Data(#"{ "axes": [ { "id": "groove", "label": "Keep the groove" } ] }"#.utf8))
        }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [SeedMockURLProtocol.self]
        let api = APIClient(baseURL: URL(string: "http://test.local")!, session: URLSession(configuration: config))
        let track = Track(trackID: "1", title: "T", artist: "A", album: "B",
                          artworkURL: URL(string: "https://e.com/a.jpg")!,
                          previewURL: URL(string: "https://e.com/a.mp3")!, score: nil)
        return SeedModel(seed: track, api: api)
    }

    @Test @MainActor func readyStatusShowsAxes() async throws {
        let model = makeModel(seedStatus: "ready")
        await model.prepare()
        #expect(model.state == .ready)
        #expect(model.axes.count == 1)
    }

    @Test @MainActor func unanalyzedStatusShowsErrorState() async throws {
        let model = makeModel(seedStatus: "unanalyzed")
        await model.prepare()
        #expect(model.state == .unanalyzed)
    }
}
