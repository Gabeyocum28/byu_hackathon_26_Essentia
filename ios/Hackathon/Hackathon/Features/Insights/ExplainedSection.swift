//
//  ExplainedSection.swift
//  Hackathon
//
//  A titled section with a "?" button that reveals what the reader is
//  actually looking at. The Math screen shows real statistics, and a chart
//  nobody can interpret is decoration — the explanation is part of the
//  feature, not documentation for it.
//

import SwiftUI

struct ExplainedSection<Content: View>: View {
    let title: String
    let explanation: String
    @ViewBuilder var content: Content

    @State private var showsExplanation = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(title)
                    .font(.headline)
                Button {
                    withAnimation(.snappy(duration: 0.2)) { showsExplanation.toggle() }
                } label: {
                    Image(systemName: showsExplanation
                          ? "questionmark.circle.fill" : "questionmark.circle")
                        .font(.subheadline)
                        .foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(showsExplanation
                                    ? "Hide explanation of \(title)"
                                    : "Explain \(title)")
                Spacer(minLength: 0)
            }

            if showsExplanation {
                Text(explanation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.quaternary.opacity(0.4), in: .rect(cornerRadius: 8))
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }

            content
        }
    }
}
