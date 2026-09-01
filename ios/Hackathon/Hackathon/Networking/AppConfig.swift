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
    /// The permanent server: the "hackathon" container on the Oracle VM.
    /// Plain HTTP — the Info.plist ATS exception for this host allows it.
    nonisolated static let baseURL = URL(string: "http://163.192.48.114:8000")!

    /// Extra headers applied to every request. (ngrok needed a skip-warning
    /// header; Cloudflare doesn't — kept as a hook for whatever tunnel is used.)
    nonisolated static let extraHeaders: [String: String] = [:]
}
