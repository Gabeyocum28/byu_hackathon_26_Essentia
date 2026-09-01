# On-demand embedding via Redis work queue — design

**Date:** 2026-09-01
**Status:** approved by Gabe (verbally, in session)

## Problem

The iOS app searches Deezer, so users can tap tracks that were never
crawled into the corpus. `POST /seed` already handles a cache miss by
downloading the preview and running `analyze_track()` — but the deployed
server is the "hackathon" container on the Oracle ARM VM, where Essentia
cannot import (no aarch64 wheels). Today that failure is swallowed
(`app.py`, the `except (NotImplementedError, ImportError)` branch): the
seed reports `"ready"` and `/recommend` silently serves fixture-fallback
results for any un-analyzed track.

Goal: when a tapped track has no embedding, compute one on Gabe's Mac
(where Essentia works), store it in the VM's Redis, and serve real
recommendations — growing the corpus one tap at a time. The app shows a
loading state while this happens and fails loudly if it can't.

## Decisions made

- **Topology: Redis work queue.** The phone talks only to the VM. The VM
  enqueues cache-miss track ids in Redis; a worker on the Mac pops jobs,
  analyzes, and writes features back. No inbound path to the Mac is
  needed — the Mac already reaches the VM's Redis (this is how
  `scripts/push_tracks.py` pushes today).
- **Failure mode: fail loudly.** If features don't appear within the
  wait window, `/seed` returns `status: "unanalyzed"` and the app shows
  an error with Retry instead of proceeding to fixture recommendations.
  The job stays queued so the corpus still grows when the worker comes
  online.
- **Contract note:** `contract/contract.md` documents only
  `status: "ready"`. Adding the `"unanalyzed"` value extends the frozen
  contract; Gabe authorized this. `contract.md` itself is NOT edited.
  The iOS decoder already treats `status` as an opaque string, so no
  decode break.
- **Ownership note:** the change spans `server/`, `scripts/`, and
  `ios/` — multiple lanes of the original working agreement. Gabe
  authorized crossing lanes.

## Architecture

```
iPhone ── POST /seed ──► VM FastAPI
                            │ features:{id} present? ── yes ──► "ready"
                            │ no
                            ├─ write track:{id}
                            ├─ LPUSH embed:queue (dedup via embed:queued)
                            ├─ poll features:{id}, 0.5s × ≤20s
                            │      appeared ──► "ready"
                            └──── timeout ──► "unanalyzed" (job stays queued)

Mac worker (scripts/embed_worker.py, REDIS_URL → VM)
    BRPOP embed:queue ─► read track:{id} (Deezer fallback)
    ─► download preview ─► analyze_track() ─► store.put_track()
    ─► SREM embed:queued
```

## Components

### 1. Redis queue keys (new, internal — not part of the HTTP contract)

| Key            | Type | Meaning                                          |
|----------------|------|--------------------------------------------------|
| `embed:queue`  | list | pending track ids; producer `LPUSH`, worker `BRPOP` |
| `embed:queued` | set  | dedup guard so double-taps enqueue once          |

Results are written to the existing keys (`features:{id}`,
`track:{id}`, `corpus:ids`) via `store.put_track()` — the server
detects completion by the appearance of `features:{id}`.

The worker clears a track's `embed:queued` membership when its job
finishes, success or failure. Because a set member can't expire on its
own, each enqueue also sets a companion TTL key `embed:queued:{id}`
(EX 300): the server skips enqueueing only while both exist. So a job
lost to a mid-job worker crash blocks re-enqueue for at most 5 minutes,
after which the next tap of that track queues it again.

### 2. Server change — `src/music_recommendations/server/app.py`

`/seed` cache-miss path, inside the existing
`except (NotImplementedError, ImportError)` branch (local analysis
stays as the first attempt so a Mac-hosted server still works):

1. `store.put_track_meta(track)` — new small store helper that writes
   `track:{id}` only (no features, no corpus membership).
2. Enqueue: if not (`SISMEMBER embed:queued` and `EXISTS
   embed:queued:{id}`): `SADD embed:queued`, `SET embed:queued:{id} 1
   EX 300`, `LPUSH embed:queue`.
3. Poll `store.get_features(track_id)` every 0.5 s, up to 20 s total.
4. Features found → `{"track_id": id, "status": "ready"}`.
5. Timeout → `{"track_id": id, "status": "unanalyzed"}` (HTTP 200 —
   the request succeeded; the analysis just isn't done).

All new Redis calls go through `store.py` helpers wrapped in the
existing `_safe()` pattern: a down Redis degrades to today's behavior
(return `"ready"`, fixture fallback), never a 500.

New `store.py` helpers: `put_track_meta(track)`,
`enqueue_embed(track_id) -> bool`, and the poll uses existing
`get_features`.

### 3. Mac worker — `scripts/embed_worker.py`

Long-running CLI, started manually on the Mac:

```
REDIS_URL=redis://<vm>:6379/0 python3 scripts/embed_worker.py
```

Loop:

1. `BRPOP embed:queue` (timeout 5 s, loop forever; Ctrl-C exits).
2. Read `track:{id}`; if missing, fetch metadata via
   `music_recommendations.server.deezer.get_track` (worker runs on the
   Mac where that import is fine).
3. Download `preview_url` to a temp file.
4. `analyze_track(mp3)` → `store.put_track(track, features)` (same
   `_to_plain` float conversion the server uses).
5. `SREM embed:queued`, `DEL embed:queued:{id}` — in a `finally`, so a
   failed job can be re-enqueued by the next tap.
6. On any per-job exception: log the track id and error, continue the
   loop. No retries, no failure queue — YAGNI for on-demand volume.

Single process, sequential jobs. Taps arrive one at a time and analysis
is ~1 s; parallelism is `push_tracks.py`'s job for bulk pushes.

Reuses: `analyze_track` from `analysis`, `store` and `deezer` from
`server`. The preview-download helper is duplicated (it is 4 lines in
`app.py`); not worth a shared module.

### 4. iOS — loading and failure state

Files: `Networking/APIClient.swift`, `Features/Seed/SeedView.swift`
(plus wherever the seed call currently originates).

- **Timeout:** the seed request uses a per-request
  `timeoutInterval` of 30 s (default URLSession config elsewhere
  unchanged).
- **Loading state:** while `/seed` is in flight, `SeedView` shows a
  progress indicator with text "Analyzing track…" replacing the axis
  buttons (they are meaningless until seeding resolves).
- **Failure state:** if `SeedResponse.status != "ready"`, show an
  inline error — "This track hasn't been analyzed yet. Is the embed
  worker running?" — with a **Retry** button that re-issues `/seed`.
  Axis buttons are not shown in this state. Transport errors (timeout,
  network) reuse the same error surface with the transport message.

No new endpoints, no polling loop on the phone: one blocking request,
exactly the contract's shape.

## Error handling summary

| Failure                         | Behavior                                              |
|---------------------------------|-------------------------------------------------------|
| Redis down (server side)        | `_safe()` → today's behavior: "ready" + fixture recs  |
| Worker offline                  | 20 s wait → `"unanalyzed"`; job embeds when worker returns |
| Worker crashes mid-job          | dedup TTL (300 s) expires; next tap re-enqueues       |
| Analysis fails on a track       | worker logs and drops; tap again re-enqueues          |
| Deezer preview download fails   | same as analysis failure                              |
| Phone timeout / network error   | iOS error surface + Retry                             |

## Testing

- **Server (pytest, stubbed store/deezer):** cache-hit returns ready
  with no enqueue; cache-miss enqueues then returns ready when features
  appear mid-poll; cache-miss returns `"unanalyzed"` after timeout
  (poll interval/timeout injectable so the test doesn't sleep 20 s);
  dedup prevents double enqueue; Redis-down degrades to legacy path.
- **Worker (pytest):** process-one-job with stubbed `analyze_track` +
  fake store writes features and clears dedup; job failure clears dedup
  and does not raise.
- **iOS (XCTest):** `SeedResponse` decodes `"unanalyzed"`; model maps
  non-ready status to the error state. Manual simulator pass for the
  spinner and Retry.

## Out of scope

Progress percentages, push notifications, a worker daemon/launchd
setup, retry queues, batch backfill (that's `push_tracks.py`), any
`contract/` file edit, auth on the queue.
