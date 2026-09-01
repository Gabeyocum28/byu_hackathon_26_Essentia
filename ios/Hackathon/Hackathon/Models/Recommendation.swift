//
//  Recommendation.swift
//  Hackathon
//
//  Navigation value pairing a chosen seed with a chosen axis. Used to drive
//  the push into the recommendation list.
//

import Foundation

struct Recommendation: Hashable {
    let seed: Track
    let axis: Axis
}
