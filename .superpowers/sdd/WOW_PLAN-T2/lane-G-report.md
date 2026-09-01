# Lane G report — iOS T2.1 Tour + T2.2 Topo + T2.4 eigen-listening

Branch: `gabe/t2-galaxy` (off `fd24bbc`, in this worktree)
Commit: `427bdca` — `feat(ios): build Grand Tour, Topology, and eigen-listening rails`
No push, no PR (as instructed — controller handles both).

## Files touched

- `ios/Hackathon/Hackathon/Models/VizT2.swift` (new)
- `ios/Hackathon/Hackathon/Networking/APIClient.swift` (added 3 methods)
- `ios/Hackathon/Hackathon/Features/Insights/TourView.swift` (new)
- `ios/Hackathon/Hackathon/Features/Insights/TopologyView.swift` (new)
- `ios/Hackathon/Hackathon/Features/Insights/EigenListeningView.swift` (new)
- `ios/Hackathon/Hackathon/Features/Insights/InsightsView.swift` (extended, per brief)
- `ios/Hackathon/HackathonTests/VizT2DecodingTests.swift` (new)
- `ios/Hackathon/HackathonTests/GivensTourFrameTests.swift` (new)
- `ios/Hackathon/HackathonTests/TopologyComponentsTests.swift` (new)

`SpectrogramView.swift` and `MelSpectrogram.swift` were not touched.
`project.pbxproj` was not touched (filesystem-synchronized groups pick up
the new files automatically).

## T2.1 — Grand Tour

Shipped the primary approach, not the slerp fallback: chained Givens
rotations `G(theta_ij(t))` for all 28 coordinate pairs in R^8, each at its
own angular speed `0.05 * sqrt(prime)` — 28 distinct primes give 28
pairwise-incommensurate speeds, so the frame never repeats. The frame is
recomputed from `t` on every call (not accumulated frame-to-frame), so
there's no drift to correct across the animation's lifetime; a
Gram-Schmidt pass still runs every call as the defensive
re-orthonormalization the brief asked for, guarding against float error
within the 28-rotation chain.

Perf: `VizTour.coords` ([[Float]], n x 8) is decoded once. Per animation
frame: compute `e1(t)`, `e2(t)` (28 rotations x 2 length-8 vectors — cheap),
then for each point two dot products into a preallocated
`TourProjectionBuffer` (a class holding `[Double]` x/y arrays sized once,
mutated in place) — no per-frame array allocation for the point set itself.
`PointTransform` is reused from `GalaxyMapView.swift` (it's not `private`,
so it's directly usable), recomputing the bounding box each frame, which is
an O(n) scan but allocation-free.

Play/pause: elapsed time is tracked as `pausedElapsed + now - playStartDate`
while playing, frozen at `pausedElapsed` while paused — no incremental
integration, so pausing/resuming can't accumulate error either.

Variance caption sums `tour.variance` (8 doubles) and multiplies by 100.

Pure math extracted to `GivensTourFrame` (static funcs, no view
dependencies) and unit tested for orthonormality across a range of `t`,
determinism at a fixed `t`, that `t=0` recovers the standard basis, and
that `project` matches direct dot products.

## T2.2 — Topology / H0 persistence

Galaxy starfield uses a static 2-d layout: PC1/PC2 straight from the same
`/viz/tour` payload (fetched once, shared with Tour mode), looked up by
track id and reordered to match `/viz/mst`'s own id order — the contract
doesn't guarantee the two endpoints return ids in the same order, so I
built an id -> (x, y) dictionary rather than assuming index alignment.

Union-find (`UnionFind`) and the threshold-to-components function
(`TopologyComponents.components`) are pure and separately tested against a
handcrafted 5-node edge list at four thresholds (nothing merged, one
merge, two of three edges, everything merged).

Recompute choice: components are recomputed from scratch on every Canvas
draw (driven by the `@State threshold` bound to the `Slider`) rather than
incrementally maintained across drags. At this corpus's edge count
(n-1, a few thousand at most) `O(n * alpha(n))` union-find is fast enough
that dragging stayed smooth in manual testing — I did not add
throttling/debouncing. If the live corpus turns out much larger, the first
thing to add would be a `.throttle`-style gate on the slider's `onEditing`
callback.

Coloring: components with size > 1 are ranked by size (largest first) and
assigned one of 12 hues (`hue = rank % 12 / 12`); singletons render as dim
white (`.white.opacity(0.25)`), matching "largest components get the most
distinct hues; singletons stay dim white."

Barcode strip: one bar per MST edge (already ascending by distance per the
contract), bar length proportional to `d / maxDistance`, thin (packed into
a fixed-height `Canvas`), with a yellow vertical line at the current
threshold and an explicit "H0 persistence" label per the brief.

MST edges are drawn as a sibling overlay inside `TopologyView` (its own
`Canvas`), not inside `GalaxyMapView` — `GalaxyMapView.swift` was left
completely untouched to minimize risk to the parallel Explore/Walk modes
it still owns.

## T2.4 — Eigen-listening rails

`EigenListeningView` renders one rail per PC in 1...4, each lazily fetching
`vizExtremes(pc:limit:4)` via `.task(id: pc)` the first time it appears in
the tree, cached in `InsightsModel.extremesByPC` (and a parallel
`extremesErrors` dict so a failed PC shows "rail unavailable" rather than
spinning forever — quiet degradation per the brief). Low-extreme tracks
render on the left, high-extreme on the right, both as tappable artwork
buttons wired to `playback.toggle(track)` through the same closure pattern
`ProofModeView`/`WalkStrip` use. Each rail's caption shows
`variance_pct`. Placed in Sound mode directly below `SpectrogramView`,
above the existing `MathPanel` — the rest of Sound mode is unchanged.

## Contract decoding notes

- `coords8`: decoded via `Data(base64Encoded:)` then a raw byte copy into
  `[Float]` (host is little-endian on all Apple simulator/device targets,
  matching the contract's explicit little-endian). Decode throws
  (`DecodingError.dataCorruptedError`) if the byte count doesn't equal
  `ids.count * 8 * MemoryLayout<Float>.size` — tested both for a valid
  blob and for a deliberately mismatched `ids` count.
- `/viz/mst` edges: each `[i, j, d]` triple decoded through an
  `unkeyedContainer` (`Int`, `Int`, `Double` positionally) since it's a
  heterogeneous JSON array, not an object.
- `/viz/extremes`: `ExtremeTrack` mirrors `VizWalk.Step` minus `x`/`y`,
  with a computed `.track` for the shared `Track` type, same pattern as
  `VizHubs.HubEntry`.

None of the three endpoints are live yet (server lane in progress per
memory notes); all decode tests use canned JSON, and the three network
calls degrade to a caption ("... could not be loaded" / "rail
unavailable") rather than crashing or spinning forever.

## Tests + verification

`xcodebuild test -project ios/Hackathon/Hackathon.xcodeproj -scheme
Hackathon -only-testing:HackathonTests -destination 'platform=iOS
Simulator,name=iPhone 17'` — **TEST SUCCEEDED**, whole `HackathonTests`
suite green (40 test cases across all 9 suites, including the pre-existing
ones — nothing regressed). New coverage: `VizT2DecodingTests` (4),
`GivensTourFrameTests` (4), `TopologyComponentsTests` (5).

One iteration needed: my first `TopologyComponentsTests` case had a wrong
manual expectation (assumed a threshold merged an edge it didn't); fixed
the test, re-ran, green.

## Concerns

- Server endpoints aren't live, so this is contract-only verification —
  worth a real end-to-end pass against the actual server lane's responses
  before demo, especially the base64 endianness assumption and whether
  `/viz/tour` and `/viz/mst` really do return overlapping id sets (the
  Topology view silently drops any mst id not found in tour's lookup,
  defaulting to (0,0), which would show as points stacked at the map
  center rather than failing loudly).
- Topology's per-draw union-find recompute is untested at real corpus
  scale (~2.6k points per the brief); flagged the throttling fallback
  above in case it stutters on device.
- `EigenListeningView` takes the whole `InsightsModel` by reference rather
  than decomposed properties (unlike `ProofModeView`/`WalkStrip`, which
  take plain data + closures) — chosen because rails need both cached data
  and a lazy-load trigger; a straightforward refactor to a
  data-plus-callback shape is possible later if the team prefers strict
  consistency with the other panels.

## Status

DONE

---

## Fix report — review findings (2026-09-01)

Review verdict: Spec PASS, Quality needs-fixes, 4 Important findings
(`.superpowers/sdd/WOW_PLAN-T2/review-G-findings.md`). All four addressed
on the same branch, same worktree. Files touched: `GalaxyMapView.swift`,
`TourView.swift`, `TopologyView.swift` (all within file-ownership limits —
`GalaxyMapView.swift` is explicitly listed as owned in the brief), plus
tests in `InsightsInteractionTests.swift`, `TopologyComponentsTests.swift`,
and new `TopologyLayoutTests.swift`.

### Finding 1 — barcode illegible at ~2639 edges

Root cause: `barHeight = max(1, size.height/edges.count - 1)` clamped to
1pt for every one of 2639 rows inside a fixed 46pt-tall strip, then rows
were placed at `y = index * (barHeight + 1)` — ~5278pt of content in a
46pt `Canvas`.

Fix: extracted `TopologyView.bucketedDeaths(_:rowCount:)`, a pure,
`internal` (testable) downsample — ascending-sorted edge weights bucketed
into at most `rowCount` slices, each bar drawn as the **max** of its
slice (never fabricated, never silently drops the largest/most
significant merge in a slice). The barcode `Canvas` now calls
`bucketedDeaths(edges.map(\.d), rowCount: Int(size.height))` and draws
exactly `bars.count` rows (`<= size.height` by construction), so it can
never overflow or silently clip regardless of edge count.

Covering tests (`TopologyLayoutTests.swift`):
- `bucketedDeathsStaysWithinStripHeightAtRealCorpusScale` — 2639
  synthetic ascending edges downsampled to `rowCount: 46`; asserts
  `bars.count == 46` and that the last bucket's max equals the true
  overall max (the biggest merge is never hidden).
- `bucketedDeathsIsNonDecreasingSinceInputIsSortedAscending` — same 2639
  edges; the bucketed bars stay monotonic, matching the underlying sorted
  data (no bucketing artifact reverses the trend).
- `bucketedDeathsWithFewerEdgesThanRowsIsOneBarPerEdge` — small inputs
  degrade to exactly the original behavior (one bar per edge).
- `bucketedDeathsOfEmptyInputIsEmpty` — no-edges guard.

Test output line: `Test case
'TopologyLayoutTests/bucketedDeathsStaysWithinStripHeightAtRealCorpusScale()'
passed`.

### Finding 2 — Grand Tour "breathes" every frame

Root cause: `draw(...)` built a fresh `PointTransform(x:, y:, size:)` from
the *current rotated projection's* min/max bounding box every animation
frame; as the 8-d cloud rotates its 2-d projected extent continuously
changes shape, so scale/center visibly pulsed.

Fix: added `PointTransform.init(radius:size:zoom:pan:)` to
`GalaxyMapView.swift` — origin-centered, scale derived from a fixed
`radius` instead of scanning point arrays. `TourView` now computes
`maxRadius` **once**, when the tour payload arrives (`ensureBuffer()`):
the max L2 norm across all rows' 8-d coordinates. This is a real bound
because (a) PCA scores are zero-mean, so any linear projection of them is
zero-mean too — the origin is always the true center, at any rotation —
and (b) projecting a vector through an orthonormal frame can never
increase its norm (Cauchy–Schwarz / projection is non-expansive), so no
rotation can ever produce a point farther from center than the original
8-d vector's own norm. `draw()` now calls
`PointTransform(radius: maxRadius, size: size)` every frame — the radius
is a stored constant, not recomputed — so scale and center are
frame-invariant while only the projected `(x, y)` per point still change.

Covering tests (`InsightsInteractionTests.swift`):
- `fixedRadiusTransformCentersTheOriginRegardlessOfProjectedExtent` —
  `place(x: 0, y: 0)` lands at the view center.
- `fixedRadiusTransformScaleDoesNotChangeWithDifferentPointSets` — two
  transforms built from the same radius place the same data point
  identically, i.e. scale/center depend only on `radius`, never on which
  points happen to be visible that frame.
- `fixedRadiusTransformPlacesAPointAtTheRadiusNearTheEdge` — a point
  exactly at the bounding radius lands at the expected fixed pixel offset
  (hand-computed: `fit=168, span=10, scale=16.8 -> 84px`).
- `explicitBoundsTransformMatchesTheArrayScanningInitializer` — sanity
  check that the new bounds-based math agrees with the existing
  array-scanning initializer for the same data (used for finding 3
  below).

Test output line: `Test case
'InsightsInteractionTests/fixedRadiusTransformScaleDoesNotChangeWithDifferentPointSets()'
passed`.

### Finding 3 — per-body-eval rebuild of the id→(x,y) lookup + per-draw union-find from scratch

Two separate costs, both fixed:

1. **id lookup + positions array**: `TopologyView.content` used to call
   `Self.positions(tour:mstIDs:)` (building a 2640-entry
   `Dictionary<String,(Double,Double)>`) inline in `body`, so it reran on
   every `threshold` `@State` tick (every slider-drag frame). Fixed:
   introduced `TopologyView.TopologyLayout` (positions, filtered edges,
   precomputed min/max bounds, missing-id count) built **once** by
   `TopologyView.buildLayout(tour:mst:)` inside a `.task` guarded by
   `layout == nil`, cached in `@State private var layout:
   TopologyLayout?`. `draw()` now takes the cached layout and never
   rebuilds the dictionary or rescans the point set for bounds — it uses
   `PointTransform.init(minX:maxX:minY:maxY:size:)` (also added to
   `GalaxyMapView.swift`) against the layout's precomputed bounds.
2. **union-find from scratch per draw**: added
   `IncrementalTopologyComponents`, a pure, testable struct that unions
   only the edges newly admitted since the last threshold (binary search
   via `edgeCount(upTo:in:)` over the ascending-sorted edge list finds how
   many edges qualify; only the delta is unioned). Moving the threshold
   backward past an applied merge still rebuilds from scratch (union-find
   has no undo), but that's the same cost the old code always paid, not a
   regression — and slider drags are usually monotonic within a gesture.
   Cached as `@State private var incremental: IncrementalTopologyComponents?`,
   built alongside `layout`.

Covering tests (`TopologyComponentsTests.swift`):
- `incrementalMatchesReferenceAcrossRisingThresholds` — for a sequence of
  rising thresholds, `IncrementalTopologyComponents` and the reference
  `TopologyComponents.components` produce the same partition (same-root
  membership; root *labels* aren't required to match between the two
  implementations).
- `incrementalMatchesReferenceWhenThresholdMovesBackward` — after
  advancing to the max threshold (`appliedEdgeCount == 4`), dropping back
  to a lower threshold still matches the reference and correctly resets
  `appliedEdgeCount` to `1`.
- `incrementalOnlyUnionsNewlyAdmittedEdgesGoingForward` — asserts
  `appliedEdgeCount` only advances when a threshold actually admits a new
  edge, and stays flat when the threshold moves within the same bracket
  (proves no redundant rework).
- `edgeCountBinarySearchMatchesLinearScan` — binary search agrees with a
  naive linear filter-count across a range of thresholds including
  below-min and above-max.

Test output line: `Test case
'TopologyComponentsTests/incrementalOnlyUnionsNewlyAdmittedEdgesGoingForward()'
passed`.

### Finding 4 — silent (0, 0) fallback for unresolved mst ids

Fix: `TopologyView.buildLayout` now tracks each mst id's resolution
explicitly — `positions: [(x: Double, y: Double)?]`, `nil` for any id not
found in the tour lookup, plus a `missingIDCount`. Any edge touching an
unresolved point is dropped from `layout.edges` (order-preserving
`compactMap`, so the ascending-by-`d` guarantee survives). `draw()` skips
`nil` positions rather than defaulting to `(0, 0)`. When
`missingIDCount > 0`, `TopologyView` now renders a caption warning
("N tracks have no position — tour/MST snapshot mismatch, those edges are
hidden") instead of staying silent.

Covering tests (`TopologyLayoutTests.swift`):
- `everyMSTIDResolvedLeavesNoMissingCountAndAllEdges` — the happy path:
  `missingIDCount == 0`, every position resolved, all edges kept.
- `mstIDMissingFromTourIsDroppedNotPlottedAtOrigin` — an mst id ("z")
  absent from the tour snapshot: asserts `missingIDCount == 1`, the
  unresolved position is `nil` (not `(0, 0)`), and the one edge touching
  it is dropped from `layout.edges` while the unaffected edge survives.

Test output line: `Test case
'TopologyLayoutTests/mstIDMissingFromTourIsDroppedNotPlottedAtOrigin()'
passed`.

### Minor items (also fixed, not required but cheap)

- `TopologyView.draw`'s per-point coloring used `ranked.firstIndex(of:)`
  (linear scan) per visible point per draw; replaced with a `rankOf:
  [Int: Int]` dictionary built once per draw from `ranked`, so per-point
  lookup is O(1).
- `mst.edges.map(\.d).max() ?? 0` (O(n) scan) replaced by `edges.last?.d`
  in `buildLayout`, relying on the contract's guaranteed ascending order
  (edges are filtered but filtering preserves order, so `.last` is still
  correct after the finding-4 fix).

### Re-verification

`xcodebuild test -project ios/Hackathon/Hackathon.xcodeproj -scheme
Hackathon -only-testing:HackathonTests -destination 'platform=iOS
Simulator,name=iPhone 17'` → **TEST SUCCEEDED**. Whole suite green: 55
test cases across 10 suites (up from 40/9 before this fix pass — added
`TopologyLayoutTests` (6 cases) and extended `TopologyComponentsTests`
(+4) and `InsightsInteractionTests` (+4)). Nothing regressed.

### Status

DONE_WITH_CONCERNS carried forward unchanged from the original report
(server endpoints still aren't live, so this remains contract-only
verification) — all 4 Important review findings are now fixed and
covered by tests.
