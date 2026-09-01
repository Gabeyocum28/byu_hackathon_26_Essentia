//
//  AppConfig.swift
//  Hackathon
//
//  The single place the server address is configured. Points at the mock
//  server during development; flip `baseURL` to the tunnel URL at integration
//  (design spec hour 16). Nothing else in the app needs to change.
//

import Foundation

enum AppConfig {
    /// Live Essencia server (Gabe's Mac via Cloudflare tunnel). The URL changes
    /// whenever the tunnel restarts — swap it here if search starts failing.
    /// HTTPS, so no ATS exception is needed.
    nonisolated static let baseURL = URL(string: "https://backup-exemption-visit-rush.trycloudflare.com")!

    /// Extra headers applied to every request. (ngrok needed a skip-warning
    /// header; Cloudflare doesn't — kept as a hook for whatever tunnel is used.)
    nonisolated static let extraHeaders: [String: String] = [:]
}
