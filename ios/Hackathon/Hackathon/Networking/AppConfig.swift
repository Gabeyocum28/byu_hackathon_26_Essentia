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
    /// Default to the deployed FastAPI server. Override with `ESSENTIA_BASE_URL`
    /// when you want to point the simulator at a different host.
    nonisolated static let baseURL: URL = {
        let env = ProcessInfo.processInfo.environment["ESSENTIA_BASE_URL"]?.trimmingCharacters(in: .whitespacesAndNewlines)
        let raw = (env?.isEmpty == false ? env : nil) ?? "http://163.192.48.114:8000"
        return URL(string: raw)!
    }()

    /// Extra headers applied to every request. (ngrok needed a skip-warning
    /// header; Cloudflare doesn't — kept as a hook for whatever tunnel is used.)
    nonisolated static let extraHeaders: [String: String] = [:]
}
