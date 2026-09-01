//
//  Axis.swift
//  Hackathon
//
//  One recommendation intention, rendered as a button. The axis list comes
//  from GET /axes and is never hardcoded in the client — the server decides
//  which buttons exist.
//

import Foundation

nonisolated struct Axis: Identifiable, Decodable, Hashable {
    let id: String
    let label: String
}
