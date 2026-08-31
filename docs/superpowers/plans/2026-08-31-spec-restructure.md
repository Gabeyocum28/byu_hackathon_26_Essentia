# Spec Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure this repo to the exact template in `Essencia_design_spec.md` §6 (contract/, `src/music_recommendations/{analysis,server,corpus}`, ios/, scripts/, per-lane CLAUDE.md), parking the old MVP under `legacy/` and migrating its reusable code into the new lanes.

**Architecture:** One Python package under `src/`, four ownership lanes each with a CLAUDE.md, a frozen HTTP contract in `contract/`, Redis for storage, numpy in-process ranking. Old MVP (mvp/, cache/, run scripts) moves wholesale to `legacy/` for reference during the sprint.

**Tech Stack:** Python 3.11, FastAPI + uvicorn, redis-py, numpy, essentia-tensorflow (analysis lane only), pytest.

**Spec:** `Essencia_design_spec.md` (repo root). The plan argues from it; read §2, §3, §6 before executing.

## Global Constraints

- Python 3.11 (`.python-version` = `3.11`; machine has 3.11.9 via pyenv).
- Never commit to `main` — all work on branch `gabe/spec-restructure`.
- `contract/` is read-only after Task 4 lands; later tasks import from it but never edit it.
- Only `src/music_recommendations/analysis/` may import essentia. `server/`, `corpus/`, `contract/`, and their tests must import and pass without essentia installed (guard essentia-dependent tests with `pytest.importorskip("essentia")`).
- Dependencies allowed: `fastapi`, `uvicorn`, `redis`, `numpy`, `essentia-tensorflow`; dev: `pytest`, `httpx`. Nothing else.
- Every `Track` object everywhere has exactly: `track_id` (str), `title`, `artist`, `album`, `artwork_url`, `preview_url`, and `score` (float, recommendation results only) — spec §3.
- Axis ids are exactly: `sounds_like`, `mood`, `genre`, `groove`, `surprise` — spec §3/§4.
- `models/` and `audio_cache/` are gitignored; `scripts/fetch_models.py` populates `models/`.
- Be polite to Deezer: reuse the preview-download retry pattern; sleep ≥0.2 s between crawl calls.
- Run `python3 -m pytest` before every commit; all tests must pass.
- uv is NOT installed on this machine. Write `pyproject.toml` (uv-compatible); use `python3 -m pip install -e ".[dev]"` for the working install. Do not try to generate `uv.lock`.

---

### Task 1: Branch, snapshot, move the old world to `legacy/`

**Files:**
- Move: `mvp/` → `legacy/mvp/`, `tests/` → `legacy/tests/`, `cache/` → `legacy/cache/`, `run_mvp.py`, `build_library_500.py`, `export_graph.py`, `essentia_demo.py`, `graph_template.html`, `pytest.ini`, `README.md` → `legacy/`
- Create: `legacy/CLAUDE.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `legacy/` reference tree; a clean root for the new skeleton. Later tasks copy code *from* `legacy/mvp/*.py` but never import it.

- [ ] **Step 1: Branch and snapshot the staged cache**

587 cache JSONs are already staged but uncommitted. Snapshot them first so nothing is lost, on the feature branch:

```bash
git checkout -b gabe/spec-restructure
git commit -m "chore: snapshot analyzed cache before spec restructure"
```

- [ ] **Step 2: Move everything old under legacy/**

```bash
mkdir legacy
git mv mvp tests cache run_mvp.py build_library_500.py export_graph.py essentia_demo.py graph_template.html pytest.ini README.md legacy/
rm -rf .pytest_cache legacy/mvp/__pycache__ legacy/tests/__pycache__
mv samples legacy/samples 2>/dev/null || true   # untracked mp3s, keep out of the way
mv library.json graph.json sound_connections.html legacy/ 2>/dev/null || true  # untracked artifacts
```

- [ ] **Step 3: Write `legacy/CLAUDE.md`**

```markdown
# legacy/ — the pre-spec MVP

Frozen reference copy of the flat MVP that predates Essencia_design_spec.md.
Do not import from it, extend it, or fix bugs in it. Copy code out of it
into your own lane if useful. It will be deleted after the sprint.
```

- [ ] **Step 4: Replace `.gitignore` with the spec §6 version, extended for legacy artifacts**

```gitignore
models/
audio_cache/
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
.env
ios/**/xcuserdata/

# legacy MVP derived artifacts
legacy/samples/
legacy/library.json
legacy/graph.json
legacy/sound_connections.html
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: move pre-spec MVP to legacy/, adopt spec .gitignore"
```

---

### Task 2: Root working agreement + lane placeholders

**Files:**
- Modify: `AGENTS.md` (replace content), `CLAUDE.md` (keep as `@AGENTS.md` pointer — existing repo convention so Codex reads the same rules)
- Create: `ios/CLAUDE.md`, `notebooks/.gitkeep`, `README.md`

**Interfaces:**
- Produces: the working agreement every agent loads; ownership boundaries for all later tasks.

- [ ] **Step 1: Replace `AGENTS.md` with the spec §6 root working agreement, verbatim, plus a pointer to the spec**

```markdown
# Working agreement

This is a 4-person, 24-hour sprint. Four people are running coding agents
against this repo at the same time. The full design is
`Essencia_design_spec.md` — read the section for your lane before coding.

## Ownership

You own exactly ONE of these folders. It was named in your task.

  ios/                                  — the iPhone app
  src/music_recommendations/server/     — the FastAPI backend
  src/music_recommendations/corpus/     — the Deezer crawler
  src/music_recommendations/analysis/   — the Essentia pipeline

You also own the matching folder under tests/ and any script in scripts/
that drives your lane.

Do not create, edit, or delete files outside the folder you own. This
includes pyproject.toml: if you need a dependency added, ask.

## contract/ is read-only

Everything in contract/ is shared by four people. Do not edit it.

If the contract appears wrong, incomplete, or blocking, STOP and tell the
human. Do not work around it. Do not add a field. Do not rename anything.
A contract change requires all four people to agree, and routing around a
mismatch silently breaks three other people's work.

## Test data

contract/fixture.json holds 30 real jazz tracks with real Deezer preview
URLs. Use it for all testing. Do not invent your own test tracks.

## Scope

This is a 24-hour sprint. Build what is asked, nothing more. No profile
screens, no explanation text, no accounts, no persistence beyond Redis,
no deployment config. If you think something extra is needed, ask.

## legacy/ is frozen

legacy/ holds the pre-spec MVP. Copy from it if useful; never import it,
never edit it.

## Merging

Commit and push small changes often. Do not sit on large diffs. Never
commit directly to main; branch as <name>/<topic> and open a PR. Run
`python3 -m pytest` before committing.
```

- [ ] **Step 2: Verify `CLAUDE.md` still reads `@AGENTS.md`** (it already does; leave it).

- [ ] **Step 3: Write `ios/CLAUDE.md`**

```markdown
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
```

- [ ] **Step 4: Write the new root `README.md`**

```markdown
# Jazz Recommender

Audio-based jazz recommendations for iPhone. Pick a track, pick what
"similar" means (sound / feeling / style / groove / surprise), get 5–10
tracks with 30 s previews. Design: `Essencia_design_spec.md`.

## Setup

    python3 -m pip install -e ".[dev]"     # or: uv sync
    python3 scripts/fetch_models.py        # downloads EffNet + heads into models/
    redis-server &                          # storage
    uvicorn music_recommendations.server.app:app --reload

## Layout

    contract/                     frozen HTTP contract + fixture (read-only)
    src/music_recommendations/    analysis / server / corpus lanes
    ios/                          SwiftUI app
    scripts/                      operator entry points
    legacy/                       pre-spec MVP, frozen reference

Tests: `python3 -m pytest`
```

- [ ] **Step 5: Commit**

```bash
touch notebooks/.gitkeep
git add -A && git commit -m "docs: root working agreement, ios lane, README"
```

---

### Task 3: Packaging — pyproject + package skeleton

**Files:**
- Create: `pyproject.toml`, `.python-version`, `src/music_recommendations/__init__.py`, `src/music_recommendations/{analysis,server,corpus}/__init__.py`, `tests/{analysis,server,corpus}/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: importable package `music_recommendations`; `pytest` configured via pyproject (replaces legacy pytest.ini).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "music-recommendations"
version = "0.1.0"
description = "Jazz recommender: Deezer previews + Essentia analysis + axis-based ranking"
requires-python = ">=3.11,<3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "redis>=5.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
analysis = ["essentia-tensorflow"]
dev = ["pytest>=8.0", "httpx>=0.27"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/music_recommendations"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-p no:flask"
```

- [ ] **Step 2: `.python-version` containing `3.11`, empty `__init__.py` files for the package and test dirs.**

- [ ] **Step 3: Install and verify import**

```bash
python3 -m pip install -e ".[dev]"
python3 -c "import music_recommendations; print('ok')"
python3 -m pytest   # collects nothing yet, exits 0/5 — no failures
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "build: one package under src/, pyproject with lane extras"
```

---

### Task 4: contract/ — the frozen seam

**Files:**
- Create: `contract/CLAUDE.md`, `contract/contract.md`, `contract/features.py`
- Test: `tests/test_contract.py`

**Interfaces:**
- Produces: `contract.features.TRACK_FIELDS` (frozenset of Track keys), `contract.features.AXES` (list of `{"id","label"}` dicts, order fixed), `contract.features.FEATURE_KEYS` (dict name → shape description of what `analyze_track` returns). `contract/` is NOT inside the package; tests/server load `contract/fixture.json` by path: `Path(__file__).resolve().parents[N] / "contract"`.

- [ ] **Step 1: `contract/CLAUDE.md`**

```markdown
# contract/ — READ-ONLY

Everything here is shared by all four people. Changing anything requires
all four to agree. If it looks wrong, STOP and ask a human — do not edit,
extend, rename, or work around it.
```

- [ ] **Step 2: `contract/contract.md`** — copy spec §3 verbatim: the four endpoints (`GET /search`, `POST /seed` synchronous, `GET /axes`, `GET /recommend`), the uniform Track JSON shape, and the three deliberate choices. Copy the exact JSON examples from `Essencia_design_spec.md` lines 141–175.

- [ ] **Step 3: `contract/features.py`**

```python
"""The shared shapes: Track fields, axis list, and what analyze_track returns.

This file is data, not logic. It is read-only (see CLAUDE.md).
"""
from __future__ import annotations

# Every Track object at every endpoint has exactly these keys.
# "score" additionally appears on recommendation results only.
TRACK_FIELDS = frozenset(
    {"track_id", "title", "artist", "album", "artwork_url", "preview_url"}
)

# GET /axes returns exactly this, in this order.
AXES = [
    {"id": "sounds_like", "label": "Sounds like this"},
    {"id": "mood",        "label": "Keep the feeling"},
    {"id": "genre",       "label": "Keep the style"},
    {"id": "groove",      "label": "Keep the groove"},
    {"id": "surprise",    "label": "Surprise me"},
]

# analyze_track(mp3_path) -> dict with exactly these keys.
# Arrays are 1-D float lists/ndarrays of the stated length; scalars are float.
FEATURE_KEYS = {
    "embedding": 1280,   # EffNet penultimate, frame-mean
    "genre": 400,        # genre_discogs400 head activations
    "moodtheme": 56,     # mtg_jamendo_moodtheme sigmoid activations
    "mood_happy": 1, "mood_sad": 1, "mood_relaxed": 1, "mood_aggressive": 1,
    "groove": 4,         # [bpm, beats_confidence, onset_rate, danceability]
}
```

- [ ] **Step 4: Write failing test `tests/test_contract.py`**

```python
import importlib.util
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[1] / "contract"


def _features():
    spec = importlib.util.spec_from_file_location("features", CONTRACT / "features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_axes_ids_match_spec():
    f = _features()
    assert [a["id"] for a in f.AXES] == [
        "sounds_like", "mood", "genre", "groove", "surprise"
    ]


def test_track_fields():
    f = _features()
    assert f.TRACK_FIELDS == {
        "track_id", "title", "artist", "album", "artwork_url", "preview_url"
    }
```

- [ ] **Step 5: Run `python3 -m pytest tests/test_contract.py -v` — must PASS (features.py written in step 3; if it fails, the contract file has a typo — fix it now, before it freezes).**

- [ ] **Step 6: Commit**

```bash
git add contract tests/test_contract.py
git commit -m "feat: frozen contract - endpoints, Track shape, axes, feature keys"
```

---

### Task 5: corpus lane — Deezer client migrated from legacy

**Files:**
- Create: `src/music_recommendations/corpus/CLAUDE.md`, `.../corpus/deezer.py`, `.../corpus/crawl.py`, `.../corpus/download.py`
- Test: `tests/corpus/test_deezer.py`, `tests/corpus/test_crawl.py`
- Reference (copy from, don't import): `legacy/mvp/deezer.py`

**Interfaces:**
- Produces: `deezer.track_to_contract(raw: dict) -> dict | None` (contract Track or None if no preview); `deezer.search_tracks(q, limit)`, `deezer.artist_top_tracks(artist_id, limit)`, `deezer.related_artists(artist_id, limit)`, `deezer.search_artist(name) -> dict | None`; `crawl.snowball(root_names: list[str], hops: int = 2, per_artist: int = 20) -> list[dict]` (deduped contract Tracks with preview); `download.download_preview(track: dict, dest_dir: Path) -> Path`. `crawl.ROOTS` = the 8 spec §2.3 root artist names.

- [ ] **Step 1: `corpus/CLAUDE.md`**

```markdown
# corpus/ — Person 3

Snowball crawler over Deezer /artist/{id}/related from 8 jazz roots
(spec §2.3), preview downloads into audio_cache/, batch ingest that calls
music_recommendations.analysis.analyze_track and writes Redis.

Rules:
- No Essentia imports; call analysis.analyze_track only (from ingest.py).
- No HTTP serving; this lane only *consumes* the Deezer API.
- Sleep ≥0.2 s between API calls; dedupe by track_id; require preview_url.
- Sprint target ~300 tracks. Do not gold-plate the crawler.
- Every track dict you produce is the contract Track shape — see
  contract/features.py TRACK_FIELDS.
```

- [ ] **Step 2: Write failing tests `tests/corpus/test_deezer.py`**

```python
from music_recommendations.corpus import deezer

RAW = {
    "id": 3135556, "title": "So What",
    "artist": {"id": 1910, "name": "Miles Davis"},
    "album": {"title": "Kind of Blue", "cover_medium": "https://img/x.jpg"},
    "preview": "https://cdn/preview.mp3",
}


def test_track_to_contract_shape():
    t = deezer.track_to_contract(RAW)
    assert t == {
        "track_id": "3135556",
        "title": "So What",
        "artist": "Miles Davis",
        "album": "Kind of Blue",
        "artwork_url": "https://img/x.jpg",
        "preview_url": "https://cdn/preview.mp3",
    }


def test_track_without_preview_is_dropped():
    assert deezer.track_to_contract({**RAW, "preview": ""}) is None
```

- [ ] **Step 3: Run `python3 -m pytest tests/corpus -v` — FAIL (module missing).**

- [ ] **Step 4: Write `corpus/deezer.py`** — start from `legacy/mvp/deezer.py` (`_get`, urllib patterns, and the 403-refresh trick in `download_preview`) and reshape `_slim` into the contract:

```python
"""Thin Deezer API client. No auth. Produces contract-shaped Track dicts."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.deezer.com"
SLEEP = 0.2  # politeness delay before every API call


def _get(path: str, **params) -> dict:
    time.sleep(SLEEP)
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def track_to_contract(raw: dict) -> dict | None:
    """Deezer track payload -> contract Track, or None if it has no preview."""
    if not raw.get("preview"):
        return None
    return {
        "track_id": str(raw["id"]),
        "title": raw["title"],
        "artist": raw["artist"]["name"],
        "album": raw.get("album", {}).get("title", ""),
        "artwork_url": raw.get("album", {}).get("cover_medium", ""),
        "preview_url": raw["preview"],
    }


def search_tracks(query: str, limit: int = 10) -> list[dict]:
    data = _get("/search", q=query, limit=limit).get("data", [])
    return [t for t in map(track_to_contract, data) if t]


def search_artist(name: str) -> dict | None:
    data = _get("/search/artist", q=name, limit=1).get("data", [])
    return {"id": data[0]["id"], "name": data[0]["name"]} if data else None


def artist_top_tracks(artist_id: int, limit: int = 20) -> list[dict]:
    data = _get(f"/artist/{artist_id}/top", limit=limit).get("data", [])
    return [t for t in map(track_to_contract, data) if t]


def related_artists(artist_id: int, limit: int = 20) -> list[dict]:
    data = _get(f"/artist/{artist_id}/related", limit=limit).get("data", [])
    return [{"id": a["id"], "name": a["name"]} for a in data]


def fresh_preview_url(track_id: str) -> str | None:
    """Preview URLs are signed and expire (~15 min); refetch for a new one."""
    return _get(f"/track/{track_id}").get("preview") or None
```

- [ ] **Step 5: Write `corpus/crawl.py`**

```python
"""Snowball crawl: 8 roots -> 2 hops of /related -> top tracks, deduped."""
from __future__ import annotations

from . import deezer

ROOTS = [
    "Miles Davis", "Duke Ellington", "Django Reinhardt", "Ornette Coleman",
    "Bill Evans", "Stan Getz", "Jimmy Smith", "Weather Report",
]


def snowball_artists(root_names: list[str], hops: int = 2, per_artist: int = 20) -> list[dict]:
    seen: dict[int, dict] = {}
    frontier = [a for a in (deezer.search_artist(n) for n in root_names) if a]
    for artist in frontier:
        seen[artist["id"]] = artist
    for _ in range(hops):
        nxt = []
        for artist in frontier:
            for rel in deezer.related_artists(artist["id"], limit=per_artist):
                if rel["id"] not in seen:
                    seen[rel["id"]] = rel
                    nxt.append(rel)
        frontier = nxt
    return list(seen.values())


def snowball(root_names: list[str] = ROOTS, hops: int = 2, per_artist: int = 20) -> list[dict]:
    """All candidate tracks (contract shape, preview required), deduped by id."""
    tracks: dict[str, dict] = {}
    for artist in snowball_artists(root_names, hops, per_artist):
        for t in deezer.artist_top_tracks(artist["id"], limit=per_artist):
            tracks.setdefault(t["track_id"], t)
    return list(tracks.values())
```

- [ ] **Step 6: Write `tests/corpus/test_crawl.py`** — pure, no network, by monkeypatching the deezer module:

```python
from music_recommendations.corpus import crawl


def test_snowball_dedupes_artists_and_tracks(monkeypatch):
    artists = {1: [{"id": 2, "name": "B"}], 2: [{"id": 1, "name": "A"}]}
    track = {
        "track_id": "9", "title": "T", "artist": "A", "album": "",
        "artwork_url": "", "preview_url": "https://p",
    }
    monkeypatch.setattr(crawl.deezer, "search_artist", lambda n: {"id": 1, "name": "A"})
    monkeypatch.setattr(crawl.deezer, "related_artists", lambda i, limit: artists.get(i, []))
    monkeypatch.setattr(crawl.deezer, "artist_top_tracks", lambda i, limit: [track])
    out = crawl.snowball(["A"], hops=2)
    assert out == [track]   # same track from both artists -> one entry
```

- [ ] **Step 7: Write `corpus/download.py`** — port `download_preview` from `legacy/mvp/deezer.py` with the 403 retry, but keyed on contract fields and saving to `audio_cache/{track_id}.mp3`:

```python
"""Preview downloads into audio_cache/. Signed URLs expire; retry once fresh."""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from . import deezer

AUDIO_CACHE = Path(__file__).resolve().parents[3] / "audio_cache"


def download_preview(track: dict, dest_dir: Path = AUDIO_CACHE) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{track['track_id']}.mp3"
    if path.exists():
        return path
    try:
        urllib.request.urlretrieve(track["preview_url"], path)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        fresh = deezer.fresh_preview_url(track["track_id"])
        if not fresh:
            raise
        track["preview_url"] = fresh
        urllib.request.urlretrieve(fresh, path)
    return path
```

- [ ] **Step 8: Run `python3 -m pytest tests/corpus -v` — PASS. Commit.**

```bash
git add src/music_recommendations/corpus tests/corpus
git commit -m "feat(corpus): contract-shaped Deezer client, snowball crawl, preview download"
```

---

### Task 6: fixture.json — 30 real jazz tracks

**Files:**
- Create: `scripts/build_fixture.py`, `contract/fixture.json` (generated)
- Test: `tests/test_contract.py` (extend)

**Interfaces:**
- Consumes: `corpus.deezer.search_artist`, `artist_top_tracks` (Task 5).
- Produces: `contract/fixture.json` = `{"tracks": [Track × 30]}`, real Deezer IDs/artwork/previews. Everyone's test data from here on.

- [ ] **Step 1: Write `scripts/build_fixture.py`**

```python
"""Build contract/fixture.json: 30 real jazz tracks from the 8 root artists.

Operator entry point — run once at hour 0, then fixture.json is frozen.
Usage: python3 scripts/build_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.corpus import deezer
from music_recommendations.corpus.crawl import ROOTS

OUT = Path(__file__).resolve().parents[1] / "contract" / "fixture.json"
TARGET = 30


def main() -> None:
    tracks: dict[str, dict] = {}
    for name in ROOTS:
        artist = deezer.search_artist(name)
        if not artist:
            continue
        for t in deezer.artist_top_tracks(artist["id"], limit=5):
            tracks.setdefault(t["track_id"], t)
            if len(tracks) >= TARGET:
                break
        if len(tracks) >= TARGET:
            break
    if len(tracks) < TARGET:
        sys.exit(f"only found {len(tracks)} tracks; wanted {TARGET}")
    OUT.write_text(json.dumps({"tracks": list(tracks.values())[:TARGET]}, indent=2))
    print(f"wrote {TARGET} tracks -> {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add failing test to `tests/test_contract.py`**

```python
import json


def test_fixture_thirty_contract_tracks():
    f = _features()
    data = json.loads((CONTRACT / "fixture.json").read_text())
    assert len(data["tracks"]) == 30
    for t in data["tracks"]:
        assert set(t) == f.TRACK_FIELDS
        assert t["preview_url"].startswith("http")
        assert isinstance(t["track_id"], str)
```

- [ ] **Step 3: Run it — FAIL (no fixture.json). Then generate: `python3 scripts/build_fixture.py` (network; takes ~10 s with politeness sleeps).**

- [ ] **Step 4: Run `python3 -m pytest tests/test_contract.py -v` — PASS. Commit.**

```bash
git add scripts/build_fixture.py contract/fixture.json tests/test_contract.py
git commit -m "feat: fixture.json - 30 real jazz tracks, everyone's test data"
```

---

### Task 7: analysis lane — registry, embedding, heads, groove

**Files:**
- Create: `src/music_recommendations/analysis/CLAUDE.md`, `.../analysis/registry.py`, `.../analysis/embedding.py`, `.../analysis/heads.py`, `.../analysis/groove.py`, `.../analysis/__init__.py` (replace empty), `scripts/fetch_models.py`
- Test: `tests/analysis/test_registry.py`, `tests/analysis/test_analyze.py`
- Reference: `legacy/mvp/analyzer.py`

**Interfaces:**
- Consumes: nothing from other lanes. `contract/features.py::FEATURE_KEYS` names the output shape.
- Produces: `analysis.analyze_track(mp3_path: Path | str) -> dict` — keys exactly `FEATURE_KEYS`: `embedding` (np.ndarray (1280,)), `genre` (400,), `moodtheme` (56,), `mood_happy/sad/relaxed/aggressive` (float), `groove` (np.ndarray (4,): bpm, beats_confidence, onset_rate, danceability). Pure: no cache, no HTTP, no Redis. `registry.HEADS: dict[str, Head]`, `registry.Head(filename, n_out, input_node, output_node)`, `registry.EFFNET_FILE`, `registry.MODELS_DIR`, `registry.model_url(filename)`.

- [ ] **Step 1: `analysis/CLAUDE.md`**

```markdown
# analysis/ — Person 4

Pure function: MP3 path in, dict of feature vectors out (spec §2.1).
Knows nothing about HTTP, Deezer, Redis, or the phone. No caching here —
Person 2 owns *when* analysis happens; you own *how*.

Rules:
- Only this lane may import essentia.
- One EffNet pass feeds every classification head. Never instantiate
  EffNet twice per track (genre is a head on the embedding, NOT
  PartitionedCall:0 on a second pass).
- Two MonoLoader decodes are correct: 16 kHz for EffNet, 44.1 kHz for
  rhythm DSP. Don't "optimize" that away.
- Head node names vary per head and bite silently. Every head lives in
  registry.py with verified input/output node names. Never assume the
  TensorflowPredict2D defaults.
- Output keys must match contract/features.py FEATURE_KEYS exactly.
- Groove extractor choices (swing, tempo folding) are open — yours to
  change freely; they live entirely inside groove.py.
```

- [ ] **Step 2: Write failing test `tests/analysis/test_registry.py`** (no essentia needed)

```python
from music_recommendations.analysis import registry


def test_verified_node_names_from_spec():
    g = registry.HEADS["genre"]
    assert g.input_node == "serving_default_model_Placeholder"
    assert g.output_node == "PartitionedCall:0"
    assert g.n_out == 400
    m = registry.HEADS["moodtheme"]
    assert m.input_node == "model/Placeholder"
    assert m.output_node == "model/Sigmoid"
    assert m.n_out == 56


def test_urls_are_wellformed():
    for head in registry.HEADS.values():
        assert registry.model_url(head.filename).startswith(
            "https://essentia.upf.edu/models/classification-heads/"
        )
```

- [ ] **Step 3: Run — FAIL. Write `analysis/registry.py`**

```python
"""One table of classification heads: file, size, verified node names.

Node names are NOT uniform across heads (spec §2.1) — every head added
here must have its names checked against the actual graph, not assumed.
fetch_models.py and heads.py both read this table; adding an axis that
rides on the embedding is a one-row diff here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"

EFFNET_FILE = "discogs-effnet-bs64-1.pb"
EFFNET_URL = (
    "https://essentia.upf.edu/models/feature-extractors/discogs-effnet/"
    + EFFNET_FILE
)
EFFNET_OUTPUT = "PartitionedCall:1"  # penultimate layer -> (n_frames, 1280)


@dataclass(frozen=True)
class Head:
    filename: str      # e.g. "genre_discogs400-discogs-effnet-1.pb"
    n_out: int
    input_node: str    # verified per head; TensorflowPredict2D default lies
    output_node: str


HEADS: dict[str, Head] = {
    "genre":           Head("genre_discogs400-discogs-effnet-1.pb", 400,
                            "serving_default_model_Placeholder", "PartitionedCall:0"),
    "moodtheme":       Head("mtg_jamendo_moodtheme-discogs-effnet-1.pb", 56,
                            "model/Placeholder", "model/Sigmoid"),
    "mood_happy":      Head("mood_happy-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_sad":        Head("mood_sad-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_relaxed":    Head("mood_relaxed-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_aggressive": Head("mood_aggressive-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
}


def model_url(filename: str) -> str:
    family = filename.split("-")[0]
    return f"https://essentia.upf.edu/models/classification-heads/{family}/{filename}"
```

- [ ] **Step 4: Run `python3 -m pytest tests/analysis/test_registry.py -v` — PASS.**

- [ ] **Step 5: Write `analysis/embedding.py`** (port the EffNet block of `legacy/mvp/analyzer.py`, lazy singleton):

```python
"""MonoLoader(16 kHz) + Discogs-EffNet -> per-frame embeddings (n, 1280)."""
from __future__ import annotations

from pathlib import Path

from .registry import EFFNET_FILE, EFFNET_OUTPUT, MODELS_DIR

_effnet = None


def effnet_frames(mp3_path: Path | str):
    """The one slow pass (~0.5 s). Everything downstream reuses its output."""
    global _effnet
    from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs

    if _effnet is None:
        _effnet = TensorflowPredictEffnetDiscogs(
            graphFilename=str(MODELS_DIR / EFFNET_FILE), output=EFFNET_OUTPUT
        )
    audio = MonoLoader(filename=str(mp3_path), sampleRate=16000)()
    return _effnet(audio)
```

- [ ] **Step 6: Write `analysis/heads.py`**

```python
"""Run every registry head over one set of EffNet frames (~0.01 s each)."""
from __future__ import annotations

import numpy as np

from .registry import HEADS, MODELS_DIR

_loaded: dict = {}


def _head(name: str):
    from essentia.standard import TensorflowPredict2D

    if name not in _loaded:
        h = HEADS[name]
        _loaded[name] = TensorflowPredict2D(
            graphFilename=str(MODELS_DIR / h.filename),
            input=h.input_node,
            output=h.output_node,
        )
    return _loaded[name]


def run_heads(effnet_frames: np.ndarray) -> dict:
    """All heads on one embedding pass. Binary heads reduce to P(positive)."""
    out: dict = {}
    for name, spec in HEADS.items():
        act = _head(name)(effnet_frames).mean(axis=0)
        out[name] = float(act[0]) if spec.n_out == 2 else act
    return out
```

(Binary mood heads: class order in the model metadata is `[positive, non_positive]` for these heads — the legacy analyzer resolved this from the JSON metadata; verify once against `models/mood_happy-discogs-effnet-1.json` when first running, and flip the index if the positive class is not index 0.)

- [ ] **Step 7: Write `analysis/groove.py`** (rhythm DSP; the only non-embedding axis)

```python
"""MonoLoader(44.1 kHz) + rhythm DSP -> groove vector.

Extractor choices here are open (spec §2.1) and private to this file:
change freely without breaking other lanes, as long as the output stays
a 1-D float vector matching contract FEATURE_KEYS["groove"].
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def groove_vector(mp3_path: Path | str) -> np.ndarray:
    """[bpm, beats_confidence, onset_rate, danceability]"""
    from essentia.standard import (
        Danceability,
        MonoLoader,
        OnsetRate,
        RhythmExtractor2013,
    )

    audio = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
    bpm, _, beats_conf, _, _ = RhythmExtractor2013(method="multifeature")(audio)
    onset_rate = float(OnsetRate()(audio)[1])
    dance = float(Danceability()(audio)[0])
    return np.array([float(bpm), float(beats_conf), onset_rate, dance])
```

- [ ] **Step 8: Write `analysis/__init__.py`**

```python
"""analyze_track: MP3 path in, dict of named feature vectors out (spec §2.1).

Pure — no cache, no HTTP, no Redis. Callers (server, corpus/ingest)
decide when to run it and where results live.
"""
from __future__ import annotations

from pathlib import Path


def analyze_track(mp3_path: Path | str) -> dict:
    from .embedding import effnet_frames
    from .groove import groove_vector
    from .heads import run_heads

    frames = effnet_frames(mp3_path)
    features = {"embedding": frames.mean(axis=0)}
    features.update(run_heads(frames))
    features["groove"] = groove_vector(mp3_path)
    return features
```

- [ ] **Step 9: Write `scripts/fetch_models.py`**

```python
"""Download EffNet + every head in analysis/registry.py into models/.

One command from checkout to working analysis. Skips files already present.
Usage: python3 scripts/fetch_models.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.analysis import registry


def fetch(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  have  {dest.name}")
        return
    print(f"  fetch {dest.name}")
    urllib.request.urlretrieve(url, dest)


def main() -> None:
    registry.MODELS_DIR.mkdir(exist_ok=True)
    fetch(registry.EFFNET_URL, registry.MODELS_DIR / registry.EFFNET_FILE)
    for head in registry.HEADS.values():
        fetch(registry.model_url(head.filename), registry.MODELS_DIR / head.filename)
    print("models ready")


if __name__ == "__main__":
    main()
```

- [ ] **Step 10: Write `tests/analysis/test_analyze.py`** — end-to-end, gated on essentia + models + a downloaded fixture preview:

```python
import numpy as np
import pytest

from music_recommendations.analysis import registry


def test_analyze_track_matches_feature_keys(tmp_path):
    pytest.importorskip("essentia")
    if not (registry.MODELS_DIR / registry.EFFNET_FILE).exists():
        pytest.skip("models/ not fetched; run scripts/fetch_models.py")

    import json
    from pathlib import Path

    from music_recommendations.analysis import analyze_track
    from music_recommendations.corpus.download import download_preview

    contract = Path(__file__).resolve().parents[2] / "contract"
    keys = json.loads((contract / "fixture.json").read_text())
    mp3 = download_preview(keys["tracks"][0], tmp_path)

    feats = analyze_track(mp3)
    assert feats["embedding"].shape == (1280,)
    assert feats["genre"].shape == (400,)
    assert feats["moodtheme"].shape == (56,)
    assert 0.0 <= feats["mood_happy"] <= 1.0
    assert feats["groove"].shape == (4,)
    assert np.isfinite(feats["groove"]).all()
```

- [ ] **Step 11: Fetch the missing moodtheme model and run**

```bash
python3 scripts/fetch_models.py         # only mtg_jamendo_moodtheme should download
python3 -m pytest tests/analysis -v     # PASS (or clean skip if essentia absent)
```

If the moodtheme download 404s, check the URL family split in `model_url` — `mtg_jamendo_moodtheme` contains dashes only in the suffix, so `filename.split("-")[0]` yields `mtg_jamendo_moodtheme.pb`-safe `mtg_jamendo_moodtheme`; if not, hardcode a `family` field on `Head`. If the binary-mood assertion fails, flip the positive index per Step 6's note.

- [ ] **Step 12: Commit**

```bash
git add src/music_recommendations/analysis tests/analysis scripts/fetch_models.py
git commit -m "feat(analysis): registry-driven EffNet pipeline - one pass, many heads, groove DSP"
```

---

### Task 8: server lane — rank, axes, store, mock-first app

**Files:**
- Create: `src/music_recommendations/server/CLAUDE.md`, `.../server/rank.py`, `.../server/axes.py`, `.../server/deezer.py`, `.../server/store.py`, `.../server/app.py`
- Test: `tests/server/test_rank.py`, `tests/server/test_axes.py`, `tests/server/test_app.py`

**Interfaces:**
- Consumes: `contract/fixture.json`, `contract.features.AXES`; `corpus.deezer.search_tracks` pattern (server gets its own thin copy — lanes don't cross-import to keep ownership clean; the search proxy is 20 lines).
- Produces: `rank.rank(seed_vec, matrix, direction=1, limit=10) -> np.ndarray` (row indices, best first); `axes.AXIS_FEATURES: dict[axis_id -> (feature_key, direction)]`; FastAPI `app` in `server/app.py` implementing the four contract routes, serving fixture tracks until Redis/corpus is populated (mock-first, spec §7 P2's highest-priority item).

- [ ] **Step 1: `server/CLAUDE.md`**

```markdown
# server/ — Person 2

FastAPI backend. Routes mirror contract/contract.md EXACTLY — same paths,
same query params, same JSON keys. The mock (fixture-serving) behavior
ships first and stays as the fallback until the corpus lands.

Rules:
- No Essentia imports; call music_recommendations.analysis.analyze_track.
  You own WHEN a track is analyzed (cache lookup, download, write-back);
  analysis owns HOW.
- Ranking is normalize + matmul + argsort in numpy, in-process. Never add
  FAISS/pgvector/ANN — pure overhead at this scale (spec §2.2).
- The axis registry in axes.py is the one table for adding/removing/
  reweighting axes.
- POST /seed is synchronous and blocking. No polling state machine.
```

- [ ] **Step 2: Write failing `tests/server/test_rank.py`**

```python
import numpy as np

from music_recommendations.server import rank


def test_rank_returns_nearest_first_excluding_none():
    matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]])
    seed = np.array([1.0, 0.0])
    idx = rank.rank(seed, matrix, limit=2)
    assert list(idx) == [0, 1]


def test_direction_minus_one_is_most_distant():
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]])
    seed = np.array([1.0, 0.0])
    idx = rank.rank(seed, matrix, direction=-1, limit=1)
    assert list(idx) == [1]


def test_scores_are_cosine():
    matrix = np.array([[2.0, 0.0]])          # normalization must kill magnitude
    seed = np.array([1.0, 0.0])
    scores = rank.scores(seed, matrix)
    assert np.allclose(scores, [1.0])
```

- [ ] **Step 3: Run — FAIL. Write `server/rank.py`**

```python
"""Normalize, matmul, argsort. Sub-millisecond at corpus scale (spec §2.2)."""
from __future__ import annotations

import numpy as np


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(norms == 0, 1.0, norms)


def scores(seed: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of seed against every row."""
    return _normalize(matrix) @ _normalize(seed[None, :])[0]


def rank(seed: np.ndarray, matrix: np.ndarray, direction: int = 1,
         limit: int = 10) -> np.ndarray:
    """Row indices, best first. direction=-1 ranks most-distant (surprise)."""
    return np.argsort(-direction * scores(seed, matrix))[:limit]
```

- [ ] **Step 4: Write `server/axes.py` + `tests/server/test_axes.py`**

```python
"""Axis registry: axis id -> (feature key in the analysis dict, direction).

THE one table for adding, removing, or reweighting an axis (spec §2.2).
Labels served by GET /axes come from contract/features.py — the client
renders whatever this sends.
"""
from __future__ import annotations

AXIS_FEATURES: dict[str, tuple[str, int]] = {
    "sounds_like": ("embedding", 1),
    "mood":        ("moodtheme", 1),
    "genre":       ("genre", 1),
    "groove":      ("groove", 1),
    "surprise":    ("embedding", -1),   # most distant by embedding cosine
}
```

```python
import importlib.util
from pathlib import Path

from music_recommendations.server.axes import AXIS_FEATURES

CONTRACT = Path(__file__).resolve().parents[2] / "contract"


def test_axis_registry_covers_contract_axes():
    spec = importlib.util.spec_from_file_location("features", CONTRACT / "features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(AXIS_FEATURES) == {a["id"] for a in mod.AXES}
    assert AXIS_FEATURES["surprise"][1] == -1
```

- [ ] **Step 5: Write `server/deezer.py`** (thin search proxy, own copy)

```python
"""Deezer search proxy for GET /search. Contract Track shape out."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://api.deezer.com"


def search(query: str, limit: int = 10) -> list[dict]:
    url = f"{API}/search?" + urllib.parse.urlencode({"q": query, "limit": limit})
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp).get("data", [])
    out = []
    for t in data:
        if not t.get("preview"):
            continue
        out.append({
            "track_id": str(t["id"]),
            "title": t["title"],
            "artist": t["artist"]["name"],
            "album": t.get("album", {}).get("title", ""),
            "artwork_url": t.get("album", {}).get("cover_medium", ""),
            "preview_url": t["preview"],
        })
    return out
```

- [ ] **Step 6: Write `server/store.py`** (Redis schema; used by ingest + app)

```python
"""Redis read/write. Keys:
  track:{id}      -> JSON: contract Track fields
  features:{id}   -> JSON: {feature_key: [floats] | float}
  corpus:ids      -> set of analyzed track ids
"""
from __future__ import annotations

import json

import numpy as np
import redis

_client: redis.Redis | None = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(decode_responses=True)
    return _client


def put_track(track: dict, features: dict) -> None:
    serial = {
        k: (v.tolist() if isinstance(v, np.ndarray) else v)
        for k, v in features.items()
    }
    r = client()
    r.set(f"track:{track['track_id']}", json.dumps(track))
    r.set(f"features:{track['track_id']}", json.dumps(serial))
    r.sadd("corpus:ids", track["track_id"])


def get_track(track_id: str) -> dict | None:
    raw = client().get(f"track:{track_id}")
    return json.loads(raw) if raw else None


def get_features(track_id: str) -> dict | None:
    raw = client().get(f"features:{track_id}")
    if raw is None:
        return None
    return {k: np.asarray(v) if isinstance(v, list) else v
            for k, v in json.loads(raw).items()}


def corpus_ids() -> list[str]:
    return sorted(client().smembers("corpus:ids"))
```

- [ ] **Step 7: Write `server/app.py`** — the four contract routes, mock-first: fixture tracks serve every response until Redis has a corpus. Real ranking wiring is Person 2's next step, not this task.

```python
"""FastAPI app. Routes mirror contract/contract.md exactly.

Mock-first (spec §7): with an empty Redis, every endpoint answers from
contract/fixture.json so the iOS app is unblocked from hour 1. Swapping in
real ranking replaces only the insides of these handlers.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from . import deezer

CONTRACT = Path(__file__).resolve().parents[3] / "contract"
FIXTURE = json.loads((CONTRACT / "fixture.json").read_text())["tracks"]
AXES = [
    {"id": "sounds_like", "label": "Sounds like this"},
    {"id": "mood",        "label": "Keep the feeling"},
    {"id": "genre",       "label": "Keep the style"},
    {"id": "groove",      "label": "Keep the groove"},
    {"id": "surprise",    "label": "Surprise me"},
]

app = FastAPI(title="jazz-recommender")


@app.get("/search")
def search(q: str):
    try:
        results = deezer.search(q)
    except Exception:            # offline dev: fall back to fixture
        results = FIXTURE
    return {"results": results}


@app.post("/seed")
def seed(body: dict):
    return {"track_id": str(body["track_id"]), "status": "ready"}


@app.get("/axes")
def axes():
    return {"axes": AXES}


@app.get("/recommend")
def recommend(track_id: str, axis: str, limit: int = 10):
    results = [
        {**t, "score": round(1.0 - i * 0.05, 2)}
        for i, t in enumerate(FIXTURE[:limit])
        if t["track_id"] != track_id
    ]
    return {"seed_track_id": track_id, "axis": axis, "results": results}
```

- [ ] **Step 8: Write `tests/server/test_app.py`** (offline — no network, no Redis)

```python
from fastapi.testclient import TestClient

from music_recommendations.server.app import app

client = TestClient(app)


def test_axes_contract():
    axes = client.get("/axes").json()["axes"]
    assert [a["id"] for a in axes] == [
        "sounds_like", "mood", "genre", "groove", "surprise"
    ]


def test_seed_synchronous_ready():
    r = client.post("/seed", json={"track_id": "3135556"}).json()
    assert r == {"track_id": "3135556", "status": "ready"}


def test_recommend_returns_scored_contract_tracks():
    r = client.get("/recommend", params={
        "track_id": "x", "axis": "groove", "limit": 5,
    }).json()
    assert r["seed_track_id"] == "x" and r["axis"] == "groove"
    assert 1 <= len(r["results"]) <= 5
    for t in r["results"]:
        assert set(t) == {"track_id", "title", "artist", "album",
                          "artwork_url", "preview_url", "score"}
```

- [ ] **Step 9: Run `python3 -m pytest tests/server -v` — PASS. Commit.**

```bash
git add src/music_recommendations/server tests/server
git commit -m "feat(server): mock-first FastAPI on the contract, numpy rank, axis registry, Redis store"
```

---

### Task 9: corpus ingest — batch analysis into Redis

**Files:**
- Create: `src/music_recommendations/corpus/ingest.py`, `scripts/build_corpus.py`, `scripts/analyze_corpus.py`
- Test: `tests/corpus/test_ingest.py`

**Interfaces:**
- Consumes: `analysis.analyze_track` (Task 7), `corpus.snowball`/`download_preview` (Task 5), `server.store.put_track` (Task 8 — storage schema is shared plumbing; ingest writes through it so server reads what corpus wrote).
- Produces: `ingest.ingest(tracks: list[dict], limit: int = 300) -> int` (count ingested); operator scripts.

- [ ] **Step 1: Write failing `tests/corpus/test_ingest.py`**

```python
from music_recommendations.corpus import ingest


def test_ingest_downloads_analyzes_stores(monkeypatch, tmp_path):
    track = {"track_id": "9", "title": "T", "artist": "A", "album": "",
             "artwork_url": "", "preview_url": "https://p"}
    stored = []
    monkeypatch.setattr(ingest, "download_preview", lambda t, d=None: tmp_path / "9.mp3")
    monkeypatch.setattr(ingest, "analyze_track", lambda p: {"embedding": [0.0]})
    monkeypatch.setattr(ingest, "put_track", lambda t, f: stored.append((t, f)))
    assert ingest.ingest([track], limit=300) == 1
    assert stored[0][0]["track_id"] == "9"


def test_ingest_survives_one_bad_track(monkeypatch, tmp_path):
    tracks = [{"track_id": str(i), "title": "T", "artist": "A", "album": "",
               "artwork_url": "", "preview_url": "https://p"} for i in (1, 2)]
    def boom(t, d=None):
        if t["track_id"] == "1":
            raise OSError("dead preview url")
        return tmp_path / "x.mp3"
    monkeypatch.setattr(ingest, "download_preview", boom)
    monkeypatch.setattr(ingest, "analyze_track", lambda p: {})
    monkeypatch.setattr(ingest, "put_track", lambda t, f: None)
    assert ingest.ingest(tracks) == 1
```

- [ ] **Step 2: Run — FAIL. Write `corpus/ingest.py`**

```python
"""Batch loop: download preview -> analyze_track -> write Redis.

Same analysis function the server calls on demand; different caller
(spec §7). Skips tracks already in Redis; one bad track never kills a run.
"""
from __future__ import annotations

from music_recommendations.analysis import analyze_track
from music_recommendations.server.store import corpus_ids, put_track

from .download import download_preview


def ingest(tracks: list[dict], limit: int = 300) -> int:
    have = set(corpus_ids())
    done = 0
    for track in tracks:
        if done >= limit:
            break
        if track["track_id"] in have:
            continue
        try:
            mp3 = download_preview(track)
            features = analyze_track(mp3)
        except Exception as exc:
            print(f"skip {track['track_id']} ({track['title']}): {exc}")
            continue
        put_track(track, features)
        done += 1
        print(f"[{done}] {track['artist']} — {track['title']}")
    return done
```

Note: `test_ingest` monkeypatches `corpus_ids` implicitly? No — add `monkeypatch.setattr(ingest, "corpus_ids", lambda: [])` to both tests so they run without Redis. Include that line in each test in Step 1.

- [ ] **Step 3: Write the operator scripts**

`scripts/build_corpus.py`:

```python
"""Snowball-crawl candidate jazz tracks and save them for analysis.
Usage: python3 scripts/build_corpus.py [hops]  ->  corpus_candidates.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.corpus.crawl import snowball

hops = int(sys.argv[1]) if len(sys.argv) > 1 else 2
tracks = snowball(hops=hops)
out = Path(__file__).resolve().parents[1] / "corpus_candidates.json"
out.write_text(json.dumps(tracks, indent=2))
print(f"{len(tracks)} candidates -> {out}")
```

`scripts/analyze_corpus.py`:

```python
"""Analyze crawled candidates into Redis (needs redis-server running).
Usage: python3 scripts/analyze_corpus.py [limit]   (default 300)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.corpus.ingest import ingest

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 300
path = Path(__file__).resolve().parents[1] / "corpus_candidates.json"
tracks = json.loads(path.read_text())
print(f"ingested {ingest(tracks, limit=limit)} tracks")
```

Add `corpus_candidates.json` to `.gitignore` (derived data).

- [ ] **Step 4: Run `python3 -m pytest tests/corpus -v` — PASS. Then full suite: `python3 -m pytest` — PASS. Commit.**

```bash
git add src/music_recommendations/corpus tests/corpus scripts .gitignore
git commit -m "feat(corpus): ingest pipeline - download, analyze, write Redis; operator scripts"
```

---

### Task 10: Wrap-up — full verification and PR

**Files:** none new.

- [ ] **Step 1: Full suite from a cold shell**

```bash
python3 -m pytest -v
```

Expected: all tests pass; analysis end-to-end test passes (essentia + models present on this machine) or skips cleanly.

- [ ] **Step 2: Boot check the mock server**

```bash
uvicorn --app-dir src music_recommendations.server.app:app --port 8000 &
sleep 2
curl -s localhost:8000/axes
curl -s "localhost:8000/recommend?track_id=x&axis=groove&limit=3"
kill %1
```

Expected: `/axes` returns the five buttons; `/recommend` returns fixture tracks with scores.

- [ ] **Step 3: Confirm tree matches spec §6** — `contract/`, `src/music_recommendations/{analysis,server,corpus}` each with CLAUDE.md, `ios/CLAUDE.md`, `scripts/{fetch_models,build_corpus,analyze_corpus,build_fixture}.py`, `tests/{analysis,server,corpus}/`, `notebooks/`, gitignored `models/` + `audio_cache/`, `legacy/` parked.

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin gabe/spec-restructure
gh pr create --title "Restructure repo to Essencia design spec layout" --body "$(cat <<'EOF'
Adopts the Essencia_design_spec.md §6 template: frozen contract/, one
package under src/ with analysis/server/corpus lanes + per-lane CLAUDE.md,
ios/ lane, operator scripts, fixture.json (30 real jazz tracks). Old MVP
parked under legacy/ (frozen, delete after sprint). Migrated: Deezer
client -> corpus, EffNet pipeline -> analysis (registry-driven heads),
mock-first FastAPI server on the contract.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_012YN6AB35EXCKodWPReJW4u
EOF
)"
```

---

## Self-review notes (done at plan time)

- **Spec coverage:** §6 tree — every file present in a task except `notebooks/discogs_style_embedding_comparison.ipynb` (an artifact of the spec authors' verification work; we don't have it — `notebooks/.gitkeep` holds the dir) and `uv.lock` (uv not installed; pyproject is uv-compatible, lock can be added when someone has uv). `contract/features.py`'s FEATURE_KEYS is this plan's freezing of the "shape agreed in hour 0" from §7 — the insides stay Person 4's.
- **Deliberate deviation:** the working agreement lives in `AGENTS.md` with `CLAUDE.md` as an `@AGENTS.md` pointer — this repo's existing convention so Codex and Claude read identical rules; spec §6 put the same text directly in CLAUDE.md.
- **Cut from migration (in legacy/ if wanted later):** Camelot/key scoring, human-readable reasons, valence/arousal via MusiCNN — all explicitly out of v1 scope (spec §1 non-goals: no harmony axis, no explanation text).
- **Type consistency check:** `track_id` is always `str`; `analyze_track` returns exactly `FEATURE_KEYS`; `Head` fields (`filename`, `n_out`, `input_node`, `output_node`) used identically in registry/heads/fetch_models; `put_track(track, features)` signature identical in store.py and ingest.py.
