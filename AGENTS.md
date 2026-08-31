# Agent rules — Essentia Music Connections

Rules for AI coding agents (Claude Code, Codex, etc.) working in this repo.
Multiple people + agents work here in parallel, so follow the workflow rules strictly.

## What this project is

Audio-based, explainable music recommendations. Deezer's public API (no auth)
supplies metadata + 30s preview MP3s; Essentia + TensorFlow models extract
audio features; pure-math scoring connects tracks with human-readable reasons
(timbre %, tempo compatibility, Camelot key wheel).

## Commands

```bash
pip install essentia-tensorflow   # heavy dep; needs Python 3.11
python3 run_mvp.py                # end-to-end demo: 20-track library + recommendations
python3 build_library_500.py 120  # bigger library build (arg = track count, default 500)
python3 export_graph.py           # library.json -> graph.json + sound_connections.html
python3 -m pytest                 # run all tests
python3 -m pytest tests/test_similarity.py -k camelot   # run a single test
```

## Architecture (read this before editing)

The pipeline is: **fetch → analyze → score → explain/visualize**.

- `mvp/deezer.py` — Deezer API client (search, charts, related artists, preview download). No auth needed.
- `mvp/analyzer.py` — Essentia feature extraction (BPM, key, embeddings, genres, moods). Results cached as JSON in `cache/<track_id>.json`, keyed by `CACHE_VERSION`. **If you change the feature schema, bump `CACHE_VERSION`** — stale entries then recompute automatically.
- `mvp/similarity.py` — pure scoring math (Camelot wheel, tempo half/double-time, cosine on embeddings). **Deliberately has no I/O and no Essentia imports** so tests stay fast — keep it that way. Score weights live here (`W_EMBEDDING`/`W_BPM`/`W_KEY`).
- `mvp/recommend.py` — ranking + human-readable explanations.
- `run_mvp.py`, `build_library_500.py` — library builders (small demo / large chart-based).
- `export_graph.py` + `graph_template.html` — renders the cached library into `sound_connections.html`.

Generated artifacts (do not hand-edit): `cache/`, `samples/`, `library.json`, `graph.json`, `sound_connections.html`.

**`cache/` IS committed on purpose**: it holds the analyzed features + 1280-dim
embeddings per track, so teammates and agents can score, recommend, and export
the graph without downloading MP3s or installing Essentia. Commit new/updated
cache JSONs when you analyze new tracks. Never hand-edit them.

## Hard rules

1. **Never commit audio or throwaway artifacts**: `samples/` (MP3s), `__pycache__/`, `library.json`, `graph.json`, `sound_connections.html`. (`cache/` is the exception — see above.)
2. **Never commit directly to `main`.** Create a feature branch (`<name>/<topic>`) and open a PR.
3. **Run `python3 -m pytest` before committing.** All tests must pass. New scoring/similarity logic needs tests in `tests/`.
4. Essentia may not be installed on every machine. Code in `mvp/similarity.py` and `mvp/recommend.py` must stay importable and testable without Essentia; only `mvp/analyzer.py` may import it.
5. Be polite to the Deezer API: keep the existing caching and sleep/backoff patterns when adding fetch code.
6. Don't re-download or re-analyze tracks unnecessarily — check `cache/` first (that's what `analyze_track` already does; go through it).
7. Keep commits small and messages descriptive; several agents work here concurrently and unreadable history multiplies merge pain.

## Style

- Python 3.11, standard library + numpy + essentia only — don't add dependencies without asking the humans.
- Module docstrings explain *what* each file extracts/computes — keep them updated when behavior changes.
- Match the existing style: type hints, `from __future__ import annotations`, module-level constants for tunables.
