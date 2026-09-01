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
    /// Live Essencia server (Gabe's Mac via ngrok). The URL changes whenever
    /// the tunnel restarts — swap it here if search starts failing. HTTPS, so
    /// no ATS exception is needed.
    nonisolated static let baseURL = URL(string: "https://1afe-128-187-112-3.ngrok-free.app")!

    /// ngrok serves a browser-warning interstitial (HTML) unless this header is
    /// present; with it, every request gets straight JSON.
    nonisolated static let extraHeaders: [String: String] = ["ngrok-skip-browser-warning": "1"]
}
