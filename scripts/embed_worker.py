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
