//
//  ContentView.swift
//  Hackathon
//
//  App root. The whole flow (search → seed → axes → recommendations) lives
//  inside SearchView's NavigationStack.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        SearchView()
    }
}

#Preview {
    ContentView()
}
