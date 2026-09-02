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
    /// Live Essencia server: Cloud Run, holding the 90,491-track corpus.
    /// Unlike the Cloudflare quick tunnel this replaced, the hostname is
    /// stable and the server does not depend on anyone's laptop being awake,
    /// so this default should no longer churn. Override it without editing
    /// code by setting ESSENTIA_BASE_URL.
    nonisolated static let baseURL: URL = {
        let env = ProcessInfo.processInfo.environment["ESSENTIA_BASE_URL"]?.trimmingCharacters(in: .whitespacesAndNewlines)
        let raw = (env?.isEmpty == false ? env : nil) ?? "https://essentia-server-438428032266.us-central1.run.app"
        return URL(string: raw)!
    }()

    /// Extra headers applied to every request. (ngrok needed a skip-warning
    /// header; Cloudflare doesn't — kept as a hook for whatever tunnel is used.)
    nonisolated static let extraHeaders: [String: String] = [:]
}
