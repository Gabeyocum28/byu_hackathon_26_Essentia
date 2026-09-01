"""Batch loop: download preview -> analyze_track -> write Redis.

Same analysis function the server calls on demand; different caller
(spec §7). Skips tracks already in Redis; one bad track never kills a run.

Downloads and analysis are bounded by different things, so they run
differently: downloads are I/O and go on threads, analysis is a TensorFlow
forward pass and goes on processes (analysis.batch.analyze_many). Working in
batches keeps both busy without holding thousands of embeddings in memory at
once -- 10k of them is ~100 MB of Python floats before anything is written.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from music_recommendations.analysis import FEATURES_VERSION
from music_recommendations.analysis.batch import analyze_many
from music_recommendations.corpus.download import download_preview
from music_recommendations.server import store

BATCH = 50
DOWNLOAD_THREADS = 8


# Stored beside the feature vectors rather than wrapping them: the server
# indexes the features dict directly (app.py `_vector`), so a nested
# {"v": ..., "f": ...} envelope would mean changing the server to read what
# this lane writes. An extra key it never looks up costs nothing.
VERSION_KEY = "_features_version"


def already_stored(track_id: str) -> bool:
    """True if this track is stored AND was analyzed by the current version.

    The version check is what makes changing a feature safe: when
    FEATURES_VERSION is bumped, stale vectors are re-analyzed instead of
    silently ranking against fresh ones in the same corpus.
    """
    try:
        stored = store.get_features(track_id)
    except Exception:
        return False
    return bool(stored) and stored.get(VERSION_KEY) == FEATURES_VERSION


def _download_batch(tracks: list[dict]) -> list[tuple[dict, Path]]:
    """Fetch previews concurrently; drop the ones with no working audio."""
    def one(track):
        try:
            return track, download_preview(track)
        except Exception:
            return track, None

    with ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as pool:
        return [(t, p) for t, p in pool.map(one, tracks) if p is not None]


def ingest(tracks: list[dict], limit: int = 300, workers: int | None = None,
           progress: bool = True) -> int:
    """Download, analyze, and store up to limit tracks; returns count ingested."""
    pending = [t for t in tracks if not already_stored(t["track_id"])][:limit]
    if not pending:
        return 0

    done = 0
    for start in range(0, len(pending), BATCH):
        batch = pending[start:start + BATCH]
        downloaded = _download_batch(batch)
        by_path = {str(path): track for track, path in downloaded}

        for path, features, error in analyze_many(list(by_path), workers=workers):
            track = by_path[path]
            if error:
                if progress:
                    print(f"  skip {track['track_id']}: {error}")
                continue
            try:
                store.put_track(track, {**features, VERSION_KEY: FEATURES_VERSION})
                done += 1
            except Exception as exc:  # noqa: BLE001 - a Redis blip is not fatal
                if progress:
                    print(f"  store failed {track['track_id']}: {exc}")
        if progress:
            print(f"  {done}/{len(pending)} stored")
    return done
