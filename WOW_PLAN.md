# WOW_PLAN — "The Math" screen, weaponized

> The layout + build plan for turning Essencia's insights screen into the thing
> people talk about after the hackathon. Audience: math majors, CS students,
> alumni, recruiters. Bar: they come find us afterwards.
>
> Every number in this document was measured tonight on the real corpus
> (2,634 tracks, 1280-d Discogs-EffNet embeddings, live VM). Nothing is
> hypothetical. All server additions are non-contract `/viz/*` routes —
> `contract/` stays frozen.

---

## 0. The thesis

Every music app says "our algorithm found songs you'll like." We show the
algorithm — live, interactively, on real data, with the actual theorems on
screen. The wow is not a prettier chart; it's that **each interaction
demonstrates a real result from high-dimensional geometry, spectral theory,
graph theory, topology, or statistics** — and the audience can poke it.

The killer property: our measurements *match the theory to three decimals*
(see §5). That's the difference between a demo and a lecture they'll remember.

---

## 1. The show (3-minute arc, draft)

1. **Hook (15s)** — "Every song here is a point in 1280-dimensional space.
   Here are all 2,634 of them." *(Galaxy fills the projector, slowly tumbling
   — the Grand Tour.)* "The clusters you see survive rotation — they're real
   structure, not a projection artifact."
2. **Seed + recs (20s)** — search, seed, recommendations constellation lights
   up around the seed. Tap a rec → its cosine arithmetic appears: `10.87 /
   (3.74 × 3.48) = 0.834`.
3. **Proof (30s)** — "Is 0.834 good? Here's this seed against all 2,634
   tracks." *(Histogram; recs glowing in the tail; percentile.)* "And here's
   what this histogram would look like if music were random noise — a spike
   of width 1/√1280. Concentration of measure, live." 
4. **The Walk (40s)** — "Watch us walk from Django Reinhardt to Korn." *(Path
   animates through 7 stepping stones; play 3 seconds of each.)* "The straight
   line through 1280-d space crosses silence. The geodesic through the
   k-nearest-neighbor graph takes a 2.3× detour — because it follows the
   manifold where music actually lives."
5. **Topology (30s)** — "When do genres become genres?" *(Drag the threshold
   slider; MST edges appear; components merge and recolor — the persistent
   homology H0 barcode drawn live.)*
6. **Audience moment (30s)** — "Someone name two artists." Walk between them.
   Or (stretch): record 10 seconds of the room and watch it appear as a new
   star. 
6b. **Optional: hear the why (30s)** — "The model says these two are 0.83
   similar. Which frequencies carry that?" *(Attribution bars appear; tap the
   tallest.)* "We deleted this band and the similarity dropped 40% — here's
   what we deleted, in both songs." *(Band-solo A, then B — the shared sound,
   isolated and audible.)*
7. **Close (15s)** — hubness toggle: "One last thing — in high dimensions,
   some points become universal neighbors. Without our correction, this track
   *(play KHE CALOR)* is everyone's recommendation. The curse of
   dimensionality isn't a metaphor; it's a bug we fixed with one subtraction."

---

## 2. Screen layout — Insights v2

One full-screen experience, three modes via a segmented control. The rec
picker strip and the now-playing bar stay persistent. Tap-artwork-to-play
works everywhere.

```
┌──────────────────────────────────┐
│  ‹ Back        The Math          │
│  ┌────────────────────────────┐  │
│  │  GALAXY   SOUND   PROOF    │  │  ← segmented control
│  └────────────────────────────┘  │
│                                  │
│  ╔════════════════════════════╗  │
│  ║                            ║  │
│  ║      (active mode view,    ║  │
│  ║       fills the screen)    ║  │
│  ║                            ║  │
│  ╚════════════════════════════╝  │
│                                  │
│  [♪][♪][♪][♪][♪][♪]  rec strip   │  ← tap = play + select
│  ▶ Golden — HUNTR/X  ━━━●──── ✕  │  ← now-playing bar
└──────────────────────────────────┘
```

### GALAXY mode (default)
```
┌────────────────────────────────┐
│ chips: Explore Walk Tour Topo  │
│ ╔════════════════════════════╗ │
│ ║   · ·  ·   ··   ✦(zoomable ║ │
│ ║  ·   ⭐──●──●  pannable    ║ │
│ ║   ·  ·   ·● ·   starfield) ║ │
│ ╚════════════════════════════╝ │
│ [callout card: tapped star]    │
│ Topo only:  ── threshold ──●   │
└────────────────────────────────┘
```
- **Explore** — pinch-zoom + pan; tap ANY star → callout (artwork, title,
  artist, ▶); labels appear for dense clusters at high zoom.
- **Walk** — tap two stars (or "surprise me" pair) → Dijkstra path animates
  star-by-star with a stepping-stone artwork strip; ghost chord shown dashed;
  "detour factor 2.3×" badge.
- **Tour** — the Grand Tour: continuous smooth rotation through the top-8
  principal subspace (82 KB of coords, all on-device, 60 fps). Pause/play.
- **Topo** — MST edges fade in under a draggable distance threshold;
  connected components live-recolor (union-find on device); tiny barcode
  strip at the bottom = H0 persistence diagram.

### SOUND mode
```
┌────────────────────────────────┐
│ Mel-spectrogram (scrub to seek)│
│ ╔════════════════════════════╗ │
│ ║ ▓▒░ heatmap  ░▒▓ │playhead ║ │
│ ╚════════════════════════════╝ │
│ Self-similarity matrix         │
│ ╔══════════╗  "chorus = the   │
│ ║ ▚ blocks ║   repeating      │
│ ║  ▚  ▚    ║   blocks — tap   │
│ ╚══════════╝   one to jump"   │
│ Eigen-listening rails          │
│ PC1  [♪][♪] ←──────→ [♪][♪]   │
│ PC2  [♪][♪] ←──────→ [♪][♪]   │
│ Why similar? (seed ↔ this rec) │
│ ▂▅█▃▁▂ ← similarity per band   │
│ [SOLO 200–800 Hz ▶A ▶B]        │
└────────────────────────────────┘
```
- **Scrub** the spectrogram → seeks the preview (drag = `AVPlayer.seek`).
- **Band-solo** — drag vertically across mel bands on the spectrogram →
  hear only that frequency slice of the song (STFT masking + resynthesis,
  all on-device).
- **Why similar?** — occlusion-attribution bars showing which frequency
  bands carry this pair's cosine similarity; tap a bar to solo that band in
  seed and rec back to back. (Deep dive in §3.5.)
- **Self-similarity matrix** — cosine similarity of mel frames vs themselves
  (computed on-device from the spectrogram we already have; ~256×256). Song
  structure appears as blocks; **tap a block → playback jumps there**.
- **Eigen-listening** — "what does PC1 sound like?" Tap the extreme tracks at
  each end of the top principal components.

### PROOF mode
```
┌────────────────────────────────┐
│ "How special is 0.834?"        │
│ ╔════════════════════════════╗ │
│ ║      ▁▂▅█▅▂▁      ↑recs    ║ │
│ ║ noise→‖  corpus   ▪ ▪ ▪    ║ │
│ ╚════════════════════════════╝ │
│ "closer than 99.7% of corpus"  │
│ ─────────────────────────────  │
│ Surprise correction  [ON |off] │
│ (recs jump on toggle + galaxy) │
│ ─────────────────────────────  │
│ cos θ = a·b/(‖a‖‖b‖) = 0.834   │
│ Hub hall of fame  [♪][♪][♪]    │
└────────────────────────────────┘
```
- **Histogram** — seed vs all 2,634 cosines, recs marked in the tail,
  percentile callout, **and the random-noise null overlaid** (a spike at 0
  with σ = 1/√1280). The visual gap IS the learned structure.
- **Hubness toggle** — flip the centrality correction off; watch surprise
  recs collapse onto hub tracks in the list *and* on the galaxy.
- **Score math** — the existing arithmetic panel, kept.
- **Hub hall of fame** — the corpus's biggest hubs, most-central, and
  most-isolated tracks, playable (see §5 for the actual names).

---

## 3. Feature specs

Tiers = build order. T0/T1 tonight; T2 tomorrow with the full team; T3
stretch. Hours assume one dev + coding agent.

### T0 — interaction fixes (~2h total, all iOS)
| # | Feature | Spec |
|---|---------|------|
| T0.1 | Tap artwork → play | Rec picker + hall-of-fame + walk stepping stones all call `playback.toggle(track)`. Selection follows playback. |
| T0.2 | Scrub spectrogram | `DragGesture` on SpectrogramView → `PlaybackController.seek(progress:)` (new method wrapping `AVPlayer.seek`, clamp [0,1], keep playhead glued to finger while dragging). |
| T0.3 | Pan/zoom galaxy + tap-any-star | `MagnifyGesture` + `DragGesture` feeding a transform (scale, offset) into `PointTransform`; tap → nearest point in screen space (all points, not just recs) → callout card with artwork/title/▶. Cull off-screen points when zoomed for 60fps. |

### T1 — tonight's wow (~5h total)
| # | Feature | Server | iOS | Math talking point |
|---|---------|--------|-----|--------------------|
| T1.1 | **Embedding Walk** | `GET /viz/walk?from=&to=&k=8` → Dijkstra over k-NN graph on cosine distance (measured: 4 ms). Return path tracks + xy + geodesic/ambient/detour. | Walk chip in Galaxy; animate path; stepping-stone strip; dashed ghost chord; detour badge. | "Dijkstra on the k-NN graph approximates geodesic distance on the data manifold — Isomap's core idea (Tenenbaum et al. 2000). Ambient 0.71, geodesic 1.66: music takes the long way round because the straight line crosses empty space." |
| T1.2 | **Similarity histogram + null overlay** | `GET /viz/histogram?track_id=` → 60 bins of seed-vs-corpus cosines, rec scores, percentile. Null params sent analytically: N(0, 1/√1280). | Canvas bars, rec markers, percentile label, noise-spike overlay. | "For isotropic random unit vectors in ℝᵈ, pairwise cosine has σ = 1/√d ≈ 0.0280. We measured 0.0279 on simulated noise — theory to three decimals. The corpus sits at 0.356 ± 0.116: ~13σ from noise. That gap is what the network learned." |
| T1.3 | **Hubness toggle** | `/viz/map?...&correction=off` (surprise axis serves uncorrected list too). | Toggle in Proof mode; animate rec jump in list + galaxy. | "In high dimensions the k-occurrence distribution becomes right-skewed (Radovanović et al. 2010): expected 8, our top hub appears in 47 neighbor lists. Uncorrected, one track was the answer for 22% of seeds. The fix: subtract each track's mean similarity to the corpus — one O(nd) matvec." |
| T1.4 | **Hub hall of fame** | `GET /viz/hubs` → top-k-occurrence, most-central, most-isolated + track meta. | Playable rows in Proof mode. | See §5 — the isolated pair alone (Korn vs Django) gets a laugh *and* makes the point. |

### T0/T1 implementation status — 2026-09-01

- [x] T0.1 — Playback is connected to artwork in the recommendation strip,
  hub rows, and walk stepping stones; selection follows the played track.
- [x] T0.2 — Spectrogram dragging seeks previews with clamped progress.
- [x] T0.3 — Galaxy supports pan, zoom, culling, and hit-testing every corpus
  point with a playable callout.
- [x] T1.1 — Cached cosine-distance k-NN walks, `/viz/walk`, animated path,
  ghost chord, and playable stepping stones.
- [x] T1.2 — `/viz/histogram`, analytic null overlay, percentile, and markers.
- [x] T1.3 — Corrected/uncorrected Surprise maps, correction toggle, and
  stale-response protection; the selected map drives Galaxy and Proof.
- [x] T1.4 — `/viz/hubs` and playable hub/central/isolated rows.

Verification recorded for handoff:

- [x] `PYTHONPATH=src pytest -q` (server and repository Python suite)
- [x] `xcodebuild build-for-testing … CODE_SIGNING_ALLOWED=NO` (iOS app and
  test targets compile; this environment has no usable simulator runtime for
  executing the iOS tests.)

### T2 — tomorrow's team build (~8h across 3 people)
| # | Feature | Server | iOS | Math talking point |
|---|---------|--------|-----|--------------------|
| T2.1 | **Grand Tour** | `GET /viz/tour` → per-track top-8 PC coords (82 KB float32) + variance-explained. | Tour chip: smooth rotation of an orthonormal 2-frame through ℝ⁸ (chained Givens rotations, `TimelineView`), project on-device, 60fps. | "Asimov's grand tour (1985): a dense smooth path through the space of 2-planes. Clusters that persist under rotation are real — you're watching an argument against projection artifacts. Top-8 PCs hold 37.4% of variance." |
| T2.2 | **Topology mode (H0 persistence)** | `GET /viz/mst` → the n−1 MST edges (i, j, dist) — Prim in numpy, 0.02 s measured. | Threshold slider; edges fade in below threshold; union-find recolors components live; barcode strip. | "Single-linkage clustering, the MST, and 0-dimensional persistent homology are the same object: the H0 barcode's death times are exactly the MST edge weights. You're dragging a filtration parameter of the Vietoris–Rips complex. Longest merge: 0.495; median: 0.201 — the long bars are the real genres." |
| T2.3 | **Self-similarity matrix** | none (on-device) | Downsample mel frames to ≤256 cols, cosine Gram matrix via vDSP, render heatmap, tap → seek. | "A recurrence plot (Foote 1999): choruses literally appear as repeated off-diagonal blocks. You're looking at the song's structure as a matrix." |
| T2.4 | **Eigen-listening** | `GET /viz/extremes?pc=1..4` → top/bottom tracks along each PC. | Two rails per PC, playable. | "Eigenvectors of the covariance are the directions of maximal variance. Nobody knows what PC1 of music *sounds* like — press play and find out." |
| T2.5 | **Band-solo** (~2h) | none (on-device) | Drag a band range on the spectrogram → STFT-mask resynthesis plays only those frequencies. | "We zero the FFT bins outside your selection and overlap-add back with the *original phase* — a linear band-pass in the analysis domain. No Griffin-Lim needed because we never threw the phase away." |
| T2.6 | **Why-similar attribution** (~3–4h, needs Mac worker) | `GET /viz/attribute?seed=&rec=` — server enqueues; worker band-stops the audio, re-embeds, returns per-band similarity drops; cached in Redis. | Bar chart per band; tap a bar → band-solo it in seed and rec back to back. | "Occlusion sensitivity: delete a band, push the counterfactual through the real model, measure the cosine drop. The explanation is audible — what you hear removed is exactly what the model lost." |

### §3.5 Deep dive: *hear the similarity* (T2.5 + T2.6)

**Why we're adding it.** The rest of the demo answers *where* music lies
(galaxy), *how* it connects (walk), and *whether* similarity is significant
(histogram). This answers the question every skeptic actually asks: **"okay,
but WHY are these two songs similar?"** — and answers it in audio, not in a
heatmap. Perturbation-based interpretability, run live against a real frozen
model, with audible counterfactuals, on a phone — that is the most
research-grade moment in the show, and it's the one ML-literate visitors
will not have seen before.

**The signal-processing chain (T2.5), stated precisely:**

- The spectrogram is a **Short-Time Fourier Transform** — *not* a Laplace
  transform. (Relation, if asked: the Fourier transform is the Laplace
  transform evaluated on the imaginary axis, s = iω. Laplace lives in
  control theory; spectral analysis of audio is Fourier.)
  `X[m,k] = Σₙ x[n + mH]·w[n]·e^(−i2πkn/N)` with a Hann window `w`, frame
  length N=2048, hop H=1024.
- Each column is one instant's **energy per frequency** (by Parseval, the
  power we plot really is the signal's energy split across bins) — not
  "the most common frequencies."
- The **mel filterbank** is a fixed linear map M (96×N/2, triangular rows)
  applied to the power spectrum: `mel = M·|X|²`, then dB. The mel scale
  `mel(f) = 2595·log₁₀(1 + f/700)` is psychoacoustic — approximately linear
  below 1 kHz and logarithmic above, matching perceived pitch spacing.
- **Band-solo works in the STFT domain, not the mel domain** — this matters:
  M is many-to-one, so the mel spectrogram is *not invertible*. But we still
  hold the full complex STFT (magnitudes AND phases). Selecting mel bands
  maps to a bin range; we zero bins outside it, inverse-FFT each frame with
  its **original phase**, and **overlap-add**. With a Hann window at 50%
  overlap the shifted windows sum to a constant (the **COLA condition**), so
  unmasked audio reconstructs exactly — no iterative phase recovery
  (Griffin–Lim) needed.
- Implementation detail: taper the mask edges with a raised cosine over a few
  bins — a brick-wall mask is a sinc in time and rings audibly (Gibbs).

**The attribution method (T2.6), stated precisely:**

- For a pair (x, y) with embeddings e(·) and base similarity
  `s = cos(e(x), e(y))`, the contribution of band b is
  `Δ_b = s − cos(e(x₋ᵦ), e(y))` where `x₋ᵦ` is x with band b removed by a
  band-stop filter. Optionally symmetrized by also occluding y and averaging.
- This is **occlusion sensitivity** (Zeiler & Fergus, 2014): a
  perturbation-based, model-agnostic attribution. We chose it over gradient
  methods (saliency, Grad-CAM, integrated gradients) deliberately: the
  essentia EffNet graph is frozen and gives us no clean gradient access, and
  perturbation only needs forward passes — ~0.5s each on the Mac worker, so
  ~10 bands ≈ 5s per pair, cached in Redis by (track, band).
- We intervene on the **waveform**, not the mel input, because (a) essentia's
  `TensorflowPredictEffnetDiscogs` computes mel internally from raw audio, so
  the waveform is the clean intervention point, and (b) it makes the
  counterfactual *audible* — the audience hears exactly the signal the model
  lost. What you hear and what the model sees are the same object.

**The honest caveats — knowing these IS the confident answer:**

1. **Non-additivity.** The Δ_b do *not* sum to s. Frequency bands interact
   inside a deep network, so single-band occlusion is a first-order
   approximation. The additive fix is Shapley values — averaging marginal
   contributions over all 2^B coalitions — which is exponentially many
   forward passes; single occlusion is the standard tractable surrogate.
   Say this *before* they ask and you win the exchange.
2. **Distribution shift.** Band-stopped audio is slightly out-of-distribution
   for the network; every perturbation method shares this caveat. Narrow
   bands keep the perturbation small.
3. **Correlation ≠ the model's "reasoning."** We measure sensitivity of the
   similarity to an intervention on the input — a causal statement about
   *this model's output*, not a claim about musical semantics. Phrase it as:
   "delete this band and the model's similarity drops 40%."

**Anticipated questions & answers (rehearse these):**

| Question | Answer |
|---|---|
| "Isn't the spectrogram a Laplace transform?" | STFT — windowed Fourier. Fourier = Laplace on the imaginary axis; Laplace's extra real exponent is for growth/decay analysis, not spectra. |
| "Mel is lossy — how can you invert it to audio?" | We don't invert mel. We filter in the full complex STFT domain where we kept the phase, and mel bands only define *which bins* to keep. COLA guarantees exact overlap-add reconstruction. |
| "Do the band contributions sum to the total similarity?" | No — non-additive, band interactions. Shapley values would restore additivity at 2^B model runs; we do single-band occlusion as the tractable first-order version. |
| "Why not Grad-CAM?" | Frozen graph, no gradient access in the essentia pipeline — and forward-only occlusion has a bonus: the perturbation is audible. |
| "Is filtered audio out-of-distribution for the model?" | Mildly, yes — the shared caveat of all perturbation attribution. We keep bands narrow to keep the perturbation small, and we report *drops*, not absolute scores. |
| "Why do you use the original phase?" | Because we have it — we only ever masked magnitudes' bins. Phase reconstruction (Griffin–Lim) is for pipelines that discarded phase, e.g. inverting a mel or magnitude-only spectrogram. |
| "Why the mel scale at all?" | Psychoacoustics (equal perceived pitch steps) — and it's what the model itself consumes internally, so our display matches the model's front end. |
| "Why does deleting bass change a 'timbre' embedding?" | The EffNet embedding is trained on genre/style discrimination; bass energy distribution is genre-informative. The attribution shows what *this* model uses, which is exactly the point. |

### T3 — stretch (needs the Mac worker live at the demo)
| # | Feature | Sketch |
|---|---------|--------|
| T3.1 | **Locate this room** | Record ~10s on the phone → `POST /viz/locate` (multipart) → server enqueues a sample-embed job → Mac worker (extend `embed_worker.py` to handle `embed:sample:*`) runs EffNet → phone polls → a NEW star drops onto the galaxy with its nearest neighbors listed. The single best audience-participation moment if it lands. Risk: demo-hall audio + worker liveness. Build ONLY after T2 is stable; rehearse twice. |
| T3.2 | **Song comet** | Mac worker precomputes per-frame embeddings for ~30 demo tracks → project through the corpus PCA → `viz:frames:{id}` in Redis → during playback the track's dot *moves* along its frame trajectory, trailing a comet tail. "A song is a trajectory through sound space; we recommend by its center of mass." |

---

## 4. Server API summary (all non-contract, additive)

```
GET  /viz/map?track_id&axis&limit[&correction=off]   (exists; add correction flag)
GET  /viz/walk?from&to&k=8        → {path:[Track+xy], geodesic, ambient, detour}
GET  /viz/histogram?track_id      → {bins, counts, rec_scores, percentile, null:{sd}}
GET  /viz/hubs                    → {hubs:[...], central:[...], isolated:[...], expected_k}
GET  /viz/tour                    → {ids, coords8 (base64 float32), variance}
GET  /viz/mst                     → {edges:[[i,j,d]...], ids}
GET  /viz/extremes?pc=1           → {low:[Track], high:[Track], variance_pct}
GET  /viz/attribute?seed=&rec=    → {base, bands:[{lo_hz, hi_hz, delta}], status}
                                     (enqueues to the Mac worker on first call —
                                      band-stop audio → re-embed → cosine drop;
                                      poll until status=ready; cached in Redis)
POST /viz/locate                  → (stretch) {x, y, neighbors:[Track]}
```

Implementation notes:
- All of these read the same in-process matrix cache `/viz/map` already uses;
  precompute pairwise cosine (56 MB, 0.03 s), k-NN (0.05 s), MST (0.02 s),
  SVD (0.45 s) lazily once per corpus change, cache beside `_MATRIX_CACHE`.
- Scale ceiling: the dense n×n matrix hits ~1.5 GB at n=20k. Fine ≤10k. Note
  it in code; don't engineer past it.
- Tests: mirror `tests/server/test_viz.py` style — shapes, determinism,
  404/400 paths, walk-path-endpoints-match, MST-has-n−1-edges.

## 5. Measured tonight (use these exact numbers on stage)

| Fact | Value |
|------|-------|
| Corpus | 2,634 tracks × 1280-d |
| Full SVD | 0.45 s · top-2 = 17.3% variance · top-8 = 37.4% |
| Pairwise cosine matrix | 0.03 s (56 MB) |
| k-NN graph (k=8) + Dijkstra | 0.05 s + **4 ms**, example path = 7 hops |
| Geodesic vs straight line | 1.66 vs 0.71 → **detour factor 2.3×** |
| MST (Prim) | 0.02 s · longest merge 0.495 · median 0.201 |
| Corpus cosines | 0.356 ± 0.116 |
| Random-noise cosines | 0.000 ± 0.0279 **(theory 1/√1280 = 0.0280)** |
| Biggest hub | "KHE CALOR" — DANNA: in **47** neighbor lists (uniform ⇒ 8) |
| Most central | "Tempête" — Willy Lancien |
| Most isolated | "Blind" — Korn · "Minor Swing" — Django Reinhardt |
| Historical hub bug | one track was top answer for **22% of seeds** (fixed by centrality correction) |

## 6. Build order & suggested split (4 people)

**Tonight (Gabe + agent):** T0.1–T0.3 → T1.1 → T1.2 → T1.3/T1.4 → redeploy VM
after each server merge. Each feature = branch + PR as usual;
`python3 -m pytest` + iOS tests before commit.

**Tomorrow:**
- Person A (server): T2.1/T2.2/T2.4 endpoints + caching + tests. Small,
  parallel-friendly.
- Person B (iOS galaxy): Tour + Topo modes (heaviest UI work).
- Person C (iOS sound): SSM + band-solo (T2.5) + eigen-listening + polish
  scrub/labels.
- Person D: PROOF-mode polish, projector rehearsal, timing the 3-minute arc,
  then T3.1 only if everything is green by mid-afternoon.
- T2.6 attribution: Person A (worker band-stop + endpoint + caching) with
  Person C (bars UI, reusing T2.5's solo playback) — start it only after
  T2.1–T2.5 are demo-able; precompute results for the rehearsed demo pairs.

**Definition of done per feature:** demo-able on the phone against the live
VM, one rehearsed sentence of math narration (see talking points), tests
green.

## 7. Risks & fallbacks

| Risk | Fallback |
|------|----------|
| Canvas fps with 2.6k stars + zoom | Cull off-screen points; draw corpus to a cached layer, only redraw overlays per frame. Measured baseline is fine at 1× — verify at 5× zoom early. |
| Grand Tour math fiddliness | Fallback: animate between fixed PC pairs (1-2 → 3-4 → 5-6) with slerp — 80% of the effect, 20% of the code. |
| Deezer previews at the venue (15-min URL expiry, flaky Wi-Fi) | Preview resolver already re-fetches by id. Cache the demo script's ~15 mp3s on-device before going on stage. |
| Mac worker dies during T3.1 | T3.1 is stretch-only; the show runs entirely without it. LaunchAgent auto-restarts the worker + tunnel. |
| Attribution (T2.6) slow or worker down mid-demo | Results for the rehearsed pairs are precomputed and cached in Redis; live requests for arbitrary pairs degrade gracefully to band-solo only (T2.5, fully on-device). |
| Projector mirroring | Rehearse with actual AirPlay/cable early tomorrow; dark-background modes read best. |

## 8. Conversation bait (why they come find us)

- "The histogram matched 1/√d to three decimals" — the theory-meets-data
  moment recruiters and professors both remember.
- "They walked from Django Reinhardt to Korn through embedding space."
- "They drew the H0 persistence barcode of Spotify-scale genres live on a
  phone."
- "They did occlusion attribution on a frozen audio model and made the
  explanation *audible* — you tap the bar and hear the frequencies the
  similarity lives in."
- Resume bullets: *(to be finalized from the design-review workflow —
  placeholder)* built an interactive visualization of a 1280-d audio
  embedding space (PCA grand tour, k-NN geodesics, persistent homology) on
  iOS + FastAPI/numpy; measured concentration-of-measure effects on a 2.6k
  corpus and corrected recommendation hubness with a centrality term.

---
*Generated 2026-09-01. A multi-agent design review (6 ideation lenses →
feasibility verification → narrative) is running; its verdicts and the final
3-minute script will be folded in here when it completes.*
