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
    /// Live Essencia server: Andrew's Mac via Cloudflare tunnel, holding the
    /// 83k-track corpus. Quick-tunnel hostnames change on every restart, so
    /// expect this default to churn — override it without editing code by
    /// setting ESSENTIA_BASE_URL (e.g. to the deployed host at
    /// http://163.192.48.114:8000).
    nonisolated static let baseURL: URL = {
        let env = ProcessInfo.processInfo.environment["ESSENTIA_BASE_URL"]?.trimmingCharacters(in: .whitespacesAndNewlines)
        let raw = (env?.isEmpty == false ? env : nil) ?? "https://tray-planes-defeat-projectors.trycloudflare.com"
        return URL(string: raw)!
    }()

    /// Extra headers applied to every request. (ngrok needed a skip-warning
    /// header; Cloudflare doesn't — kept as a hook for whatever tunnel is used.)
    nonisolated static let extraHeaders: [String: String] = [:]
}
