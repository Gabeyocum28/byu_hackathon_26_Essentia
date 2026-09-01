"""Pop embed jobs off the VM's Redis, run Essentia locally, write back.

The ARM VM can't import essentia, so /seed queues cold tracks instead of
analyzing them; this worker is the other half. Run it on a machine where
essentia imports (the Mac), pointed at the VM's Redis:

    REDIS_URL=redis://<vm-ip>:6379/0 python3 scripts/embed_worker.py

One process, one job at a time: on-demand taps trickle in and analysis is
~1 s. Bulk backfill stays push_tracks.py's job.
"""
from __future__ import annotations

import os
import tempfile
import time
import urllib.request
from pathlib import Path

from music_recommendations.analysis import analyze_track
from music_recommendations.server import deezer, store


def download_preview(url: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    path = Path(name)
    with urllib.request.urlopen(url, timeout=10) as resp:
        path.write_bytes(resp.read())
    return path


def _to_plain(features: dict) -> dict:
    return {
        k: v.tolist() if hasattr(v, "tolist") else v for k, v in features.items()
    }


def _fresh_track(track_id: str) -> dict | None:
    """Prefer a fresh Deezer fetch over the stored record: preview URLs
    expire in ~15 min (hdnea token), so a job that waited in the queue
    would 403 on download if we trusted the URL /seed stored."""
    try:
        track = deezer.get_track(track_id)
    except Exception:
        track = None
    return track or store.get_track(track_id)


def process_job(track_id: str) -> bool:
    """Analyze one queued track. True on success; logs and swallows failures
    so one bad track never kills the loop."""
    try:
        track = _fresh_track(track_id)
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


def _tick() -> None:
    """One loop iteration: dequeue and process a job, if there is one.

    process_job never raises, but store.dequeue_embed can (a transient Redis
    ConnectionError on the blocking pop) -- guard it here so main()'s loop
    survives a Redis blip instead of dying.
    """
    try:
        track_id = store.dequeue_embed(timeout=5)
        if track_id:
            process_job(track_id)
    except Exception as exc:
        print(f"[embed_worker] queue error {exc}, retrying in 5s", flush=True)
        time.sleep(5)


def main() -> None:
    print("[embed_worker] watching embed:queue (Ctrl-C to stop)", flush=True)
    while True:
        _tick()


if __name__ == "__main__":
    main()
