//
//  VizAttributionDecodingTests.swift
//  HackathonTests
//
//  GET /viz/attribute (T2.6) is a mailbox: it answers `pending` until the
//  worker has run the counterfactuals, so the client has to decode all
//  three states, not just the happy one.
//

import Foundation
import Testing

@testable import Hackathon

struct VizAttributionDecodingTests {
    private func decode(_ json: String) throws -> VizAttribution {
        try JSONDecoder().decode(VizAttribution.self, from: Data(json.utf8))
    }

    @Test func pendingHasNoBandsYet() throws {
        let payload = try decode(#"{"status":"pending"}"#)

        #expect(payload.isPending)
        #expect(!payload.isReady)
        #expect(payload.bands == nil)
        #expect(payload.base == nil)
    }

    @Test func readyDecodesBandsAndBaseCosine() throws {
        let payload = try decode("""
        {"status":"ready","base":0.834,"bands":[
          {"lo_hz":60.0,"hi_hz":103.6,"delta":0.031},
          {"lo_hz":103.6,"hi_hz":178.9,"delta":0.402}
        ]}
        """)

        #expect(payload.isReady)
        #expect(payload.base == 0.834)
        #expect(payload.bands?.count == 2)
        #expect(payload.bands?[1].loHz == 103.6)
        #expect(payload.bands?[1].delta == 0.402)
        // Bars scale against the biggest drop, not the sum: occlusion
        // deltas are non-additive.
        #expect(payload.largestDrop == 0.402)
    }

    @Test func failureFromTheWorkerIsReadable() throws {
        let payload = try decode(#"{"status":"failed","error":"no preview"}"#)

        #expect(!payload.isReady)
        #expect(!payload.isPending)
        #expect(payload.error == "no preview")
    }

    @Test func negativeDropsDoNotDriveTheBarScale() throws {
        let payload = try decode("""
        {"status":"ready","base":0.5,"bands":[
          {"lo_hz":60.0,"hi_hz":103.6,"delta":-0.02}
        ]}
        """)

        // Removing a band can nudge a pair closer; that explains nothing,
        // so the scale floor stays at zero rather than going negative.
        #expect(payload.largestDrop == 0)
    }

    @Test func bandAxisLabelsStayCompact() {
        #expect(WhySimilarView.label(240) == "240")
        #expect(WhySimilarView.label(1200) == "1.2k")
        #expect(WhySimilarView.label(7800) == "7.8k")
    }
}
