# ios/ — Person 1

SwiftUI iPhone app: search field → results list with artwork → tap to
select → five buttons rendered from GET /axes → recommendation list →
AVPlayer preview playback.

Rules:
- No Python. Talk to the server over HTTP only, per contract/contract.md.
- One Track struct, decoded identically at every endpoint (uniform shape).
- Render whatever buttons /axes returns — never hardcode the axis list.
- Build against the mock server + contract/fixture.json until hour 16.
- Create JazzRec.xcodeproj here via Xcode.
