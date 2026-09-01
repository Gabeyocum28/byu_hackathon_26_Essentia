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
    /// Mock server default. Override for the real backend at integration time.
    nonisolated static let baseURL = URL(string: "http://localhost:8000")!
}
