"""The corpus as files, for hosts that have no Redis.

Redis is where the crawler and the server meet on the Mac, but it cannot
travel: the corpus occupies ~3.6 GB there (vectors stored as JSON text), and
no free managed tier is within an order of magnitude of that. scripts/
export_snapshot.py freezes the same corpus into ~460 MB of files that ship
with the image, and this module reads them.

Set CORPUS_SNAPSHOT to the directory to switch the read path over; leave it
unset and store.py talks to Redis exactly as before. The Mac keeps Redis --
the crawler and embed worker still need somewhere to write.

A snapshot is immutable, but /seed is not: a track seeded on the host is
analyzed there and must join the corpus for the rest of the process's life.
Those land in an in-memory overlay that reads see layered on top of the
files. The overlay dies with the process, which is the honest bargain of a
free host with no persistent disk -- the 90k base is always there, and a
re-seed costs one preview download and one analysis.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import numpy as np

DIR_ENV = "CORPUS_SNAPSHOT"
KEY = "embedding"

_lock = threading.Lock()
_loaded: dict | None = None

# Tracks seeded at runtime: id -> contract fields / id -> {KEY: vector}.
_overlay_tracks: dict[str, dict] = {}
_overlay_features: dict[str, dict] = {}


def directory() -> Path | None:
    value = os.environ.get(DIR_ENV, "").strip()
    return Path(value) if value else None


def active() -> bool:
    """True when the server should read files rather than Redis."""
    return directory() is not None


def _load() -> dict:
    """Read the snapshot once. Cheap: the matrix is memory-mapped, not copied."""
    global _loaded
    with _lock:
        if _loaded is not None:
            return _loaded
        base = directory()
        if base is None:
            raise RuntimeError(f"{DIR_ENV} is not set")
        ids = json.loads((base / "ids.json").read_text())
        tracks = json.loads((base / "tracks.json").read_text())
        if len(ids) != len(tracks):
            raise RuntimeError(
                f"snapshot is inconsistent: {len(ids)} ids, {len(tracks)} tracks"
            )
        # mmap: startup does not wait for 442 MB, and the pages the ranking
        # actually touches are faulted in by the first request.
        matrix = np.load(base / f"{KEY}.npy", mmap_mode="r")
        if matrix.shape[0] != len(ids):
            raise RuntimeError(
                f"snapshot is inconsistent: {matrix.shape[0]} rows, {len(ids)} ids"
            )
        _loaded = {
            "ids": ids,
            # id -> row. A list.index() per lookup is a linear scan over 90k,
            # and /recommend looks up per track.
            "row": {track_id: i for i, track_id in enumerate(ids)},
            "matrix": matrix,
            "tracks": {t["track_id"]: t for t in tracks},
        }
        return _loaded


def reset() -> None:
    """Drop cached state. For tests, which point DIR_ENV at fixtures."""
    global _loaded, _ids_cache
    with _lock:
        _loaded = None
    _ids_cache = None
    _overlay_tracks.clear()
    _overlay_features.clear()
    _previews.clear()


# ---- reads (mirrors the store.py functions of the same name) ----

# Sorting 90k ids and re-deriving the overlay on every /recommend is pure
# overhead: the base never changes and the overlay only grows, so the answer
# is reusable until something is seeded.
_ids_cache: tuple[int, list[str]] | None = None


def corpus_ids() -> list[str]:
    """Every analyzed id: the frozen base plus anything seeded since boot."""
    global _ids_cache
    data = _load()
    if _ids_cache is not None and _ids_cache[0] == len(_overlay_features):
        return _ids_cache[1]
    extra = [i for i in _overlay_features if i not in data["row"]]
    ids = sorted(data["ids"] + extra) if extra else list(data["ids"])
    _ids_cache = (len(_overlay_features), ids)
    return ids


def corpus_size() -> int:
    return len(corpus_ids())


def base_matrix() -> tuple[list[str], np.ndarray]:
    """The frozen rows and their ids, in row order.

    The whole point of the snapshot: app.py takes this array as-is instead of
    reassembling 90k rows from 90k per-track lookups, which is the cost the
    Redis path had to cache its way around.
    """
    data = _load()
    return list(data["ids"]), data["matrix"]


def get_track(track_id: str) -> dict | None:
    if track_id in _overlay_tracks:
        return dict(_overlay_tracks[track_id])
    track = _load()["tracks"].get(track_id)
    return dict(track) if track else None


def get_many_tracks(track_ids: list[str]) -> list[dict | None]:
    return [get_track(t) for t in track_ids]


def get_features(track_id: str) -> dict | None:
    if track_id in _overlay_features:
        return dict(_overlay_features[track_id])
    data = _load()
    row = data["row"].get(track_id)
    if row is None:
        return None
    return {KEY: np.asarray(data["matrix"][row])}


def get_many_features(track_ids: list[str]) -> list[dict | None]:
    return [get_features(t) for t in track_ids]


# ---- writes (overlay only; the files are never modified) ----

def put_track(track: dict, features: dict) -> None:
    track_id = track["track_id"]
    _overlay_tracks[track_id] = dict(track)
    _overlay_features[track_id] = {
        k: v for k, v in features.items() if k == KEY
    }


def put_track_meta(track: dict) -> None:
    _overlay_tracks[track["track_id"]] = dict(track)


# ---- signed preview URL cache ----
#
# Redis holds this on the Mac. Without it every play would re-sign, and
# Deezer throttles, so the same 10-minute cache lives in memory here.

_previews: dict[str, tuple[str, float]] = {}
_PREVIEW_TTL_S = 600


def get_cached_preview(track_id: str) -> str | None:
    hit = _previews.get(track_id)
    if hit is None:
        return None
    url, expires = hit
    if time.monotonic() >= expires:
        _previews.pop(track_id, None)
        return None
    return url


def put_cached_preview(track_id: str, url: str,
                       ttl: int = _PREVIEW_TTL_S) -> None:
    _previews[track_id] = (url, time.monotonic() + ttl)
