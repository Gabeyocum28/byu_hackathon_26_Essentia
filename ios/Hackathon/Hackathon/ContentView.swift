//
//  ContentView.swift
//  Hackathon
//
//  App root. The whole flow (search → seed → axes → recommendations) lives
//  inside SearchView's NavigationStack. The player is owned here, outside that
//  stack, so the play bar survives every push and pop.
//

import SwiftUI

struct ContentView: View {
    @State private var playback = PlaybackController()

    var body: some View {
        SearchView()
            .safeAreaInset(edge: .bottom) {
                NowPlayingBar()
            }
            .environment(playback)
            .preferredColorScheme(.dark)
    }
}

#Preview {
    ContentView()
}
