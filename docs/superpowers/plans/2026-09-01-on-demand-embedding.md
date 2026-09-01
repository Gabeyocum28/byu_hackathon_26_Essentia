# On-Demand Embedding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user taps a Deezer search result with no embedding in Redis, a worker on Gabe's Mac analyzes it on demand; the app shows a loading state and fails loudly if analysis doesn't finish.

**Architecture:** The phone talks only to the VM server. On a `/seed` cache miss where Essentia can't run locally, the server writes track metadata to Redis, pushes the track id onto an `embed:queue` list (TTL-guarded dedup), and polls `features:{id}` for up to 20s. `scripts/embed_worker.py` runs on the Mac with `REDIS_URL` pointed at the VM, BRPOPs jobs, runs `analyze_track()`, and writes back via `store.put_track()`. Timeout returns `status: "unanalyzed"`; iOS shows an error + Retry for any non-`"ready"` status.

**Tech Stack:** FastAPI + redis-py (server), Essentia via `music_recommendations.analysis` (worker), SwiftUI + URLSession (iOS), pytest + Swift Testing.

**Spec:** `docs/superpowers/specs/2026-09-01-on-demand-embedding-design.md`

## Global Constraints

- `contract/` files are never edited. The `"unanalyzed"` status value is authorized by Gabe but `contract.md` itself stays untouched.
- All server-side Redis access goes through `music_recommendations/server/store.py`; all fallible store calls in `app.py` go through `_safe()`. A down Redis must degrade to today's behavior (status `"ready"`, fixture fallback), never a 500 and never a 20s hang.
- Stdlib `urllib` for HTTP in Python (no new runtime deps — pyproject.toml is off-limits).
- Timing values, exact: server wait 20s, poll interval 0.5s, dedup TTL 300s, worker BRPOP timeout 5s, iOS seed request timeout 30s.
- Run `python3 -m pytest` from the repo root before every commit (pre-existing suite must stay green).
- New Swift files are picked up automatically (`PBXFileSystemSynchronizedRootGroup`) — do NOT edit `project.pbxproj`.
- Match surrounding code style: module docstrings explaining "why", comments only for non-obvious constraints.

---

### Task 1: Queue helpers in store.py

**Files:**
- Modify: `src/music_recommendations/server/store.py` (append after `get_many_features`)
- Modify: `tests/server/conftest.py` (extend `FakeRedis`)
- Test: `tests/server/test_store.py` (append)

**Interfaces:**
- Consumes: existing `store.client()`.
- Produces (used by Tasks 2 and 3):
  - `put_track_meta(track: dict) -> None` — writes `track:{id}` only (no features, no corpus membership).
  - `enqueue_embed(track_id: str) -> bool` — pushes onto `embed:queue` unless dedup-guarded; returns True if pushed.
  - `dequeue_embed(timeout: int = 5) -> str | None` — BRPOP one id, None on timeout.
  - `clear_embed_marker(track_id: str) -> None` — clears the dedup guard.

- [ ] **Step 1: Extend FakeRedis with list/set/TTL ops**

In `tests/server/conftest.py`, replace the `FakeRedis` class with:

```python
class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.sets = {}
        self.lists = {}

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def mget(self, keys):
        return [self.kv.get(k) for k in keys]

    def exists(self, key):
        return 1 if key in self.kv else 0

    def delete(self, key):
        self.kv.pop(key, None)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def srem(self, key, *values):
        self.sets.get(key, set()).difference_update(values)

    def sismember(self, key, value):
        return value in self.sets.get(key, set())

    def smembers(self, key):
        return self.sets.get(key, set())

    def lpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)

    def brpop(self, key, timeout=0):
        items = self.lists.get(key)
        return (key, items.pop(0)) if items else None
```

(`ex` is accepted and ignored: the fake never expires keys; the one test that needs expiry deletes the TTL key by hand.)

- [ ] **Step 2: Write the failing tests**

Append to `tests/server/test_store.py`:

```python
# ---- embed queue ----

def test_put_track_meta_writes_track_only(fake_redis):
    track = {"track_id": "9", "title": "T", "artist": "A", "album": "B",
             "artwork_url": "u", "preview_url": "p"}
    store.put_track_meta(track)
    assert store.get_track("9") == track
    assert store.get_features("9") is None
    assert "9" not in store.corpus_ids()


def test_enqueue_embed_pushes_and_guards(fake_redis):
    assert store.enqueue_embed("9") is True
    assert store.enqueue_embed("9") is False          # dedup guard holds
    assert fake_redis.lists["embed:queue"] == ["9"]


def test_enqueue_embed_repushes_after_ttl_expiry(fake_redis):
    store.enqueue_embed("9")
    fake_redis.delete("embed:queued:9")               # simulate TTL expiry
    assert store.enqueue_embed("9") is True
    assert fake_redis.lists["embed:queue"] == ["9", "9"]


def test_dequeue_embed_pops_oldest_then_none(fake_redis):
    store.enqueue_embed("1")
    store.enqueue_embed("2")
    assert store.dequeue_embed(timeout=1) == "1"
    assert store.dequeue_embed(timeout=1) == "2"
    assert store.dequeue_embed(timeout=1) is None


def test_clear_embed_marker_allows_reenqueue(fake_redis):
    store.enqueue_embed("9")
    store.clear_embed_marker("9")
    assert store.enqueue_embed("9") is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/server/test_store.py -v`
Expected: the five new tests FAIL with `AttributeError: module ... has no attribute 'put_track_meta'` (etc.); pre-existing tests still pass.

- [ ] **Step 4: Implement the helpers**

Append to `src/music_recommendations/server/store.py`:

```python
# ---- embed work queue (internal; not part of the HTTP contract) ----
#   embed:queue        -> list of track ids awaiting analysis (LPUSH/BRPOP)
#   embed:queued       -> set guarding against duplicate enqueues
#   embed:queued:{id}  -> TTL companion: a set member can't expire on its
#                         own, so a crashed worker blocks re-enqueue for at
#                         most this long.

_QUEUED_TTL_S = 300


def put_track_meta(track: dict) -> None:
    """Write a track's contract fields only — no features, no corpus entry."""
    client().set(f"track:{track['track_id']}", json.dumps(track))


def enqueue_embed(track_id: str) -> bool:
    """Queue a track for the embed worker. False if already queued."""
    r = client()
    if r.sismember("embed:queued", track_id) and r.exists(f"embed:queued:{track_id}"):
        return False
    r.sadd("embed:queued", track_id)
    r.set(f"embed:queued:{track_id}", "1", ex=_QUEUED_TTL_S)
    r.lpush("embed:queue", track_id)
    return True


def dequeue_embed(timeout: int = 5) -> str | None:
    """Block up to `timeout` seconds for the next queued track id."""
    popped = client().brpop("embed:queue", timeout=timeout)
    return popped[1] if popped else None


def clear_embed_marker(track_id: str) -> None:
    """Drop the dedup guard so the track can be enqueued again."""
    r = client()
    r.srem("embed:queued", track_id)
    r.delete(f"embed:queued:{track_id}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/server/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add src/music_recommendations/server/store.py tests/server/conftest.py tests/server/test_store.py
git commit -m "feat(server): Redis embed work-queue helpers in store"
```

---

### Task 2: /seed enqueues and waits; "unanalyzed" on timeout

**Files:**
- Modify: `src/music_recommendations/server/app.py` (the `seed()` route and new helpers below it)
- Test: `tests/server/test_app.py` (the `/seed` section)

**Interfaces:**
- Consumes: `store.put_track_meta(track)`, `store.enqueue_embed(track_id) -> bool`, existing `store.get_features` (all from Task 1).
- Produces: `POST /seed` may now return `{"track_id": ..., "status": "unanalyzed"}` (HTTP 200). Module constants `_EMBED_WAIT_S = 20.0`, `_EMBED_POLL_S = 0.5` (tests monkeypatch these).

- [ ] **Step 1: Rewrite the /seed tests**

In `tests/server/test_app.py`, DELETE `test_seed_fixture_fallback_when_analysis_unavailable` (its "silently ready" behavior is exactly what this feature removes) and add in its place:

```python
@pytest.fixture
def analysis_unavailable(monkeypatch):
    """The ARM-VM condition: essentia can't import, plus instant poll timing."""
    def not_implemented(path):
        raise NotImplementedError

    monkeypatch.setattr(app_module, "analyze_track", not_implemented)
    monkeypatch.setattr(app_module, "_download_preview", lambda url: Path("/tmp/x.mp3"))
    monkeypatch.setattr(app_module, "_EMBED_WAIT_S", 0.0)
    monkeypatch.setattr(app_module, "_EMBED_POLL_S", 0.0)


def test_seed_enqueues_and_reports_unanalyzed_on_timeout(
        client, fake_redis, analysis_unavailable, monkeypatch):
    track = dict(FIXTURE[0])
    tid = track["track_id"]
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(track))

    body = client.post("/seed", json={"track_id": tid})
    assert body.status_code == 200
    assert body.json() == {"track_id": tid, "status": "unanalyzed"}
    # metadata stored for the worker, job queued, but corpus untouched
    assert store.get_track(tid) == track
    assert fake_redis.lists["embed:queue"] == [tid]
    assert tid not in store.corpus_ids()


def test_seed_ready_when_worker_delivers_features(
        client, fake_redis, analysis_unavailable, monkeypatch):
    track = dict(FIXTURE[1])
    tid = track["track_id"]
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(track))
    # First get_features call (the warm check) misses and plants the
    # features, as if the worker finished during the wait; later polls hit.
    real_get = store.get_features
    monkeypatch.setattr(app_module, "_EMBED_WAIT_S", 1.0)
    polled = {"n": 0}

    def get_features_then_appear(track_id):
        polled["n"] += 1
        if polled["n"] == 1:
            store.put_track(track, fake_features(0.5))
            return None
        return real_get(track_id)

    monkeypatch.setattr(store, "get_features", get_features_then_appear)
    body = client.post("/seed", json={"track_id": tid}).json()
    assert body == {"track_id": tid, "status": "ready"}


def test_seed_double_tap_enqueues_once(
        client, fake_redis, analysis_unavailable, monkeypatch):
    track = dict(FIXTURE[2])
    tid = track["track_id"]
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(track))
    client.post("/seed", json={"track_id": tid})
    client.post("/seed", json={"track_id": tid})
    assert fake_redis.lists["embed:queue"] == [tid]


def test_seed_redis_down_degrades_to_ready(client, monkeypatch):
    """No fake_redis fixture: store.client() raises -> legacy mock-first path."""
    def no_redis():
        raise ConnectionError("redis down")

    monkeypatch.setattr(store, "client", no_redis)
    monkeypatch.setattr(app_module, "_EMBED_WAIT_S", 0.0)
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(FIXTURE[3]))
    monkeypatch.setattr(app_module, "_download_preview", lambda url: Path("/tmp/x.mp3"))

    def not_implemented(path):
        raise NotImplementedError

    monkeypatch.setattr(app_module, "analyze_track", not_implemented)
    tid = FIXTURE[3]["track_id"]
    body = client.post("/seed", json={"track_id": tid}).json()
    assert body == {"track_id": tid, "status": "ready"}
```

Note on `test_seed_ready_when_worker_delivers_features`: the first poll plants the features and returns None (miss), every later poll reads them back — verifying `/seed` keeps polling and flips to ready. `fake_features` and `FIXTURE` already exist at the top of this test file.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m pytest tests/server/test_app.py -v`
Expected: the four new tests FAIL (`/seed` still answers `"ready"` and never touches `embed:queue`); everything else passes.

- [ ] **Step 3: Implement the enqueue-and-wait path**

In `src/music_recommendations/server/app.py`, add `import time` to the stdlib imports, then replace the body of `seed()`'s `try/except` (currently `except (NotImplementedError, ImportError): pass`) and add the helpers:

```python
    try:
        mp3 = _download_preview(track["preview_url"])
        features = _to_plain(analyze_track(mp3))
        _safe(store.put_track, track, features)
    except (NotImplementedError, ImportError):
        # Analysis can't run on this host (no aarch64 essentia wheels on the
        # ARM VM). Hand the job to the Mac embed worker via Redis and wait.
        return _seed_via_worker(req.track_id, track)
    return ready
```

And below the `seed()` route:

```python
# How long /seed waits for the embed worker before failing loudly. Module
# constants so tests can shrink them instead of sleeping 20 real seconds.
_EMBED_WAIT_S = 20.0
_EMBED_POLL_S = 0.5


def _seed_via_worker(track_id: str, track: dict) -> dict:
    _safe(store.put_track_meta, track)
    queued = _safe(store.enqueue_embed, track_id)
    if queued is None:
        # Redis is down: there is no queue to hand to and no features to
        # await. Mock-first as before -- "ready", fixture-fallback recs.
        return {"track_id": track_id, "status": "ready"}
    status = "ready" if _await_features(track_id) else "unanalyzed"
    return {"track_id": track_id, "status": status}


def _await_features(track_id: str) -> bool:
    """Poll until the worker writes features:{id}, or the wait window closes."""
    deadline = time.monotonic() + _EMBED_WAIT_S
    while True:
        if _safe(store.get_features, track_id) is not None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_EMBED_POLL_S)
```

(The check-before-deadline ordering means a zero wait still polls once.)

- [ ] **Step 4: Run the full server suite**

Run: `python3 -m pytest tests/server/ -v`
Expected: ALL PASS. Then run `python3 -m pytest` (whole repo) — ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/music_recommendations/server/app.py tests/server/test_app.py
git commit -m "feat(server): /seed queues cold tracks for the embed worker, returns unanalyzed on timeout"
```

---

### Task 3: Mac embed worker script

**Files:**
- Create: `scripts/embed_worker.py`
- Test: `tests/server/test_embed_worker.py`

**Interfaces:**
- Consumes: `store.dequeue_embed(timeout)`, `store.clear_embed_marker(track_id)`, `store.get_track`, `store.put_track`, `deezer.get_track`, `music_recommendations.analysis.analyze_track`.
- Produces: `process_job(track_id: str) -> bool` (True on success, never raises) and a `main()` BRPOP loop. Run as `REDIS_URL=redis://<vm-ip>:6379/0 python3 scripts/embed_worker.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/server/test_embed_worker.py` (script loaded by path, same pattern as `test_push_tracks.py`):

```python
"""embed_worker.py: pop queued tracks, analyze locally, write back to Redis."""
import importlib.util
from pathlib import Path

import pytest

from music_recommendations.server import store

SCRIPT = Path(__file__).parents[2] / "scripts" / "embed_worker.py"
spec = importlib.util.spec_from_file_location("embed_worker", SCRIPT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

TRACK = {
    "track_id": "42",
    "title": "Blue in Green",
    "artist": "Miles Davis",
    "album": "Kind of Blue",
    "artwork_url": "http://x/a.jpg",
    "preview_url": "http://x/p.mp3",
}
FEATURES = {"embedding": [0.1, 0.2], "groove": [120.0, 0.9, 3.1, 0.5]}


@pytest.fixture
def analysis_ok(monkeypatch, tmp_path):
    mp3 = tmp_path / "p.mp3"
    mp3.write_bytes(b"mp3")
    monkeypatch.setattr(worker, "download_preview", lambda url: mp3)
    monkeypatch.setattr(worker, "analyze_track", lambda p: dict(FEATURES))


def test_process_job_analyzes_stores_and_clears_marker(fake_redis, analysis_ok):
    store.put_track_meta(TRACK)
    store.enqueue_embed("42")

    assert worker.process_job("42") is True
    assert store.get_features("42") == FEATURES
    assert "42" in store.corpus_ids()
    assert store.enqueue_embed("42") is True   # marker cleared -> re-enqueueable


def test_process_job_falls_back_to_deezer_for_metadata(fake_redis, analysis_ok, monkeypatch):
    monkeypatch.setattr(worker.deezer, "get_track", lambda t: dict(TRACK))
    assert worker.process_job("42") is True
    assert store.get_track("42") == TRACK


def test_process_job_failure_logs_clears_marker_never_raises(fake_redis, monkeypatch):
    def boom(url):
        raise OSError("download failed")

    store.put_track_meta(TRACK)
    store.enqueue_embed("42")
    monkeypatch.setattr(worker, "download_preview", boom)

    assert worker.process_job("42") is False
    assert store.get_features("42") is None
    assert store.enqueue_embed("42") is True   # marker cleared despite failure


def test_process_job_no_metadata_anywhere_fails_cleanly(fake_redis, monkeypatch):
    monkeypatch.setattr(worker.deezer, "get_track", lambda t: None)
    assert worker.process_job("42") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/server/test_embed_worker.py -v`
Expected: collection ERROR — `scripts/embed_worker.py` does not exist.

- [ ] **Step 3: Write the worker**

Create `scripts/embed_worker.py`:

```python
"""Pop embed jobs off the VM's Redis, run Essentia locally, write back.

The ARM VM can't import essentia, so /seed queues cold tracks instead of
analyzing them; this worker is the other half. Run it on a machine where
essentia imports (the Mac), pointed at the VM's Redis:

    REDIS_URL=redis://<vm-ip>:6379/0 python3 scripts/embed_worker.py

One process, one job at a time: on-demand taps trickle in and analysis is
~1 s. Bulk backfill stays push_tracks.py's job.
"""
from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

from music_recommendations.analysis import analyze_track
from music_recommendations.server import deezer, store


def download_preview(url: str) -> Path:
    path = Path(tempfile.mkstemp(suffix=".mp3")[1])
    with urllib.request.urlopen(url, timeout=10) as resp:
        path.write_bytes(resp.read())
    return path


def _to_plain(features: dict) -> dict:
    return {
        k: v.tolist() if hasattr(v, "tolist") else v for k, v in features.items()
    }


def process_job(track_id: str) -> bool:
    """Analyze one queued track. True on success; logs and swallows failures
    so one bad track never kills the loop."""
    try:
        track = store.get_track(track_id) or deezer.get_track(track_id)
        if track is None:
            print(f"[embed_worker] {track_id}: no metadata in Redis or on Deezer", flush=True)
            return False
        mp3 = download_preview(track["preview_url"])
        try:
            features = _to_plain(analyze_track(mp3))
        finally:
            mp3.unlink(missing_ok=True)
        store.put_track(track, features)
        print(f"[embed_worker] {track_id}: analyzed  {track['artist']} - {track['title']}", flush=True)
        return True
    except Exception as exc:
        print(f"[embed_worker] {track_id}: FAILED  {exc}", flush=True)
        return False
    finally:
        # Always drop the dedup guard: a failed job should be re-enqueueable
        # by the next tap, not stuck behind a stale marker.
        try:
            store.clear_embed_marker(track_id)
        except Exception:
            pass


def main() -> None:
    print("[embed_worker] watching embed:queue (Ctrl-C to stop)", flush=True)
    while True:
        track_id = store.dequeue_embed(timeout=5)
        if track_id:
            process_job(track_id)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/server/test_embed_worker.py -v` then `python3 -m pytest`
Expected: ALL PASS.

Note: loading the worker module imports `music_recommendations.analysis`; if `analyze_track`'s essentia import is lazy (it is — the server relies on catching `ImportError` at call time), collection works everywhere. If collection fails on a machine without essentia, that machine can't run this test — fine; the Mac and CI can.

- [ ] **Step 5: Commit**

```bash
git add scripts/embed_worker.py tests/server/test_embed_worker.py
git commit -m "feat(scripts): embed_worker — Mac-side consumer for the embed queue"
```

---

### Task 4: iOS — 30s seed timeout, unanalyzed state, Retry

**Files:**
- Modify: `ios/Hackathon/Hackathon/Networking/APIClient.swift`
- Modify: `ios/Hackathon/Hackathon/Features/Seed/SeedView.swift`
- Test: `ios/Hackathon/HackathonTests/APIClientTests.swift` (append)
- Test: Create `ios/Hackathon/HackathonTests/SeedModelTests.swift`

**Interfaces:**
- Consumes: `SeedResponse.status: String` (already decoded); server may now send `"unanalyzed"`.
- Produces: `SeedModel.LoadState` gains `case unanalyzed`; the seed request carries `timeoutInterval = 30`.

- [ ] **Step 1: Write the failing tests**

Append to the `APIClientTests` suite in `ios/Hackathon/HackathonTests/APIClientTests.swift`:

```swift
    @Test func seedDecodesUnanalyzedStatus() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{ "track_id": "3135556", "status": "unanalyzed" }"#.utf8))
        }
        let response = try await makeClient().seed(trackID: "3135556")
        #expect(response.status == "unanalyzed")
    }

    @Test func seedRequestAllowsThirtySecondWait() async throws {
        MockURLProtocol.handler = { _ in
            (200, Data(#"{ "track_id": "1", "status": "ready" }"#.utf8))
        }
        _ = try await makeClient().seed(trackID: "1")
        #expect(MockURLProtocol.lastRequest?.timeoutInterval == 30)
    }
```

Also create `ios/Hackathon/HackathonTests/SeedModelTests.swift` (picked up automatically — no pbxproj edit):

```swift
//
//  SeedModelTests.swift
//  HackathonTests
//
//  SeedModel maps the /seed status to a view state: "ready" shows axis
//  buttons, anything else is the unanalyzed error state.
//

import Foundation
import Testing
@testable import Hackathon

@Suite(.serialized)
struct SeedModelTests {

    private func makeModel(seedStatus: String) -> SeedModel {
        MockURLProtocol.handler = { request in
            if request.url!.path.hasSuffix("/seed") {
                return (200, Data(#"{ "track_id": "1", "status": "\#(seedStatus)" }"#.utf8))
            }
            return (200, Data(#"{ "axes": [ { "id": "groove", "label": "Keep the groove" } ] }"#.utf8))
        }
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let api = APIClient(baseURL: URL(string: "http://test.local")!, session: URLSession(configuration: config))
        let track = Track(trackID: "1", title: "T", artist: "A", album: "B",
                          artworkURL: URL(string: "https://e.com/a.jpg")!,
                          previewURL: URL(string: "https://e.com/a.mp3")!, score: nil)
        return SeedModel(seed: track, api: api)
    }

    @Test @MainActor func readyStatusShowsAxes() async throws {
        let model = makeModel(seedStatus: "ready")
        await model.prepare()
        #expect(model.state == .ready)
        #expect(model.axes.count == 1)
    }

    @Test @MainActor func unanalyzedStatusShowsErrorState() async throws {
        let model = makeModel(seedStatus: "unanalyzed")
        await model.prepare()
        #expect(model.state == .unanalyzed)
    }
}
```

Notes for the implementer: `LoadState` needs to be `Equatable` for `#expect(model.state == .ready)` — add `enum LoadState: Equatable` in Step 4 (it is a plain enum; conformance is free). If `Track`'s memberwise init differs (check `Models/Track.swift`), construct it with whatever initializer exists — the field values don't matter to these tests. `MockURLProtocol` is the one already defined in `APIClientTests.swift`, same target.

- [ ] **Step 2: Run the iOS tests to verify the new tests fail**

Run (from `ios/Hackathon`):
```bash
xcodebuild test -project Hackathon.xcodeproj -scheme Hackathon \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  -only-testing:HackathonTests 2>&1 | tail -20
```
(If no "iPhone 17" simulator exists, list with `xcrun simctl list devices available` and substitute.)
Expected: the test target FAILS TO COMPILE (`SeedModelTests` references `.unanalyzed`, which doesn't exist yet). That is the red state; if you want a runnable red first, comment out `SeedModelTests` temporarily and observe `seedRequestAllowsThirtySecondWait` FAIL (default timeoutInterval is 60). `seedDecodesUnanalyzedStatus` passes already (status is an opaque String) — fine, it pins the contract.

- [ ] **Step 3: Add the timeout to the seed request**

In `APIClient.swift`, give `post` an optional timeout and pass it from `seed`:

```swift
    /// POST /seed { track_id }. Blocking on the server: warm instant, cold
    /// up to ~20s while the embed worker analyzes — hence the long timeout.
    @discardableResult
    func seed(trackID: String) async throws -> SeedResponse {
        try await post("seed", body: ["track_id": trackID], as: SeedResponse.self, timeout: 30)
    }
```

```swift
    private func post<T: Decodable>(_ path: String, body: [String: String], as type: T.Type, timeout: TimeInterval? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        if let timeout { request.timeoutInterval = timeout }
        return try await send(request, as: type)
    }
```

- [ ] **Step 4: Surface the unanalyzed state in SeedModel/SeedView**

In `SeedView.swift`, extend the model:

```swift
    enum LoadState: Equatable {
        case preparing
        case ready
        case unanalyzed
        case failed
    }
```

and in `prepare()` use the seed response instead of discarding it:

```swift
    func prepare() async {
        state = .preparing
        do {
            // Absorb the blocking seed analysis while the axes load.
            async let seeded = api.seed(trackID: seed.trackID)
            async let axesList = api.axes()
            let seedResponse = try await seeded
            axes = try await axesList
            state = seedResponse.status == "ready" ? .ready : .unanalyzed
        } catch {
            state = .failed
        }
    }
```

In the view's `switch`, update the loading copy and add the new case:

```swift
            case .preparing:
                ProgressView("Analyzing track…")
            case .unanalyzed:
                RetryView(message: "This track hasn't been analyzed yet. Is the embed worker running?") {
                    Task { await model.prepare() }
                }
            case .failed:
                RetryView(message: "Couldn't prepare this track.") {
                    Task { await model.prepare() }
                }
            case .ready:
                AxisButtons(seed: model.seed, axes: model.axes)
```

- [ ] **Step 5: Run the iOS test suite**

Run the same `xcodebuild test` command as Step 2.
Expected: ALL PASS (including both new tests).

- [ ] **Step 6: Commit**

```bash
git add ios/Hackathon/Hackathon/Networking/APIClient.swift ios/Hackathon/Hackathon/Features/Seed/SeedView.swift ios/Hackathon/HackathonTests/APIClientTests.swift
git commit -m "feat(ios): 30s seed timeout + unanalyzed state with retry"
```

---

### Task 5: End-to-end smoke test against the real stack

Manual verification, no code. Requires: VM server redeployed with Tasks 1-2 (rebuild/restart the "hackathon" container), Mac worker running.

- [ ] **Step 1: Start the worker on the Mac**

```bash
REDIS_URL=redis://163.192.48.114:6379/0 python3 scripts/embed_worker.py
```
(Use the same `REDIS_URL` that `scripts/push_tracks.py` runs use today; if Redis is only reachable through an SSH tunnel, open that tunnel first and point at localhost.)

- [ ] **Step 2: Cold seed via curl**

Pick any track id from a `/search` response that is NOT in the corpus, then:

```bash
curl -s -X POST http://163.192.48.114:8000/seed \
  -H 'Content-Type: application/json' -d '{"track_id": "<id>"}'
```
Expected: blocks a few seconds, worker prints `analyzed`, response is `{"track_id": "<id>", "status": "ready"}`. Repeat the same curl — instant `"ready"`. `GET /recommend?track_id=<id>&axis=sounds_like` returns scored results, not fixture fallback.

- [ ] **Step 3: Worker-offline path**

Stop the worker, seed another cold track. Expected: ~20s block, then `"status": "unanalyzed"`. Restart the worker — it drains the queued job. The same curl now returns `"ready"` instantly.

- [ ] **Step 4: Phone**

Run the app from Xcode, search a song not in the corpus, tap it: spinner with "Analyzing track…", then axis buttons. With the worker stopped, tapping a cold track shows the unanalyzed message with Retry; starting the worker and tapping Retry proceeds.
