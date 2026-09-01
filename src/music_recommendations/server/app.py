"""FastAPI app. Routes mirror contract/contract.md exactly. Mock-first: serve
contract/fixture.json until the corpus lands.

Routes:
  GET  /search      -- query Deezer (or fixture fallback) for tracks
  POST /seed         -- mark a track as the seed for recommendations
  GET  /axes         -- list available recommendation axes
  GET  /recommend    -- ranked, scored tracks for a seed + axis
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import NamedTuple

from contract.features import AXES
from music_recommendations.analysis import analyze_track
from music_recommendations.analysis.schema import METRICS
from music_recommendations.server import deezer, store, viz
from music_recommendations.server.axes import AXIS_FEATURES

app = FastAPI(title="Essencia")

_FIXTURE_PATH = Path(__file__).parents[3] / "contract" / "fixture.json"


def _fixture_tracks() -> list[dict]:
    return json.loads(_FIXTURE_PATH.read_text())["tracks"]


def _fixture_track(track_id: str) -> dict | None:
    return next(
        (t for t in _fixture_tracks() if t["track_id"] == track_id), None
    )


def _download_preview(url: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    path = Path(name)
    with urllib.request.urlopen(url, timeout=10) as resp:
        path.write_bytes(resp.read())
    return path


def _safe(fn, *args, default=None):
    """store call, but a down Redis means mock-first fallback, not a 500."""
    try:
        return fn(*args)
    except Exception:
        return default


class SeedRequest(BaseModel):
    track_id: str


@app.get("/")
def root() -> dict:
    """Signpost only — not part of the contract."""
    return {
        "service": "Essencia",
        "routes": [
            "GET /search?q=<query>",
            "POST /seed {track_id}",
            "GET /axes",
            "GET /recommend?track_id=<id>&axis=<axis>&limit=<n>",
        ],
    }


@app.get("/axes")
def get_axes() -> dict:
    return {"axes": AXES}


@app.get("/search")
def search(q: str) -> dict:
    try:
        return {"results": deezer.search(q)}
    except Exception:
        needle = q.lower()
        hits = [
            t for t in _fixture_tracks()
            if needle in t["title"].lower()
            or needle in t["artist"].lower()
            or needle in t["album"].lower()
        ]
        return {"results": hits}


@app.post("/seed")
def seed(req: SeedRequest) -> dict:
    ready = {"track_id": req.track_id, "status": "ready"}
    if _safe(store.get_features, req.track_id) is not None:
        return ready

    track = _safe(store.get_track, req.track_id)
    if track is None:
        try:
            track = deezer.get_track(req.track_id)
        except Exception:
            track = None
    if track is None:
        track = _fixture_track(req.track_id)
    if track is None:
        raise HTTPException(404, f"track {req.track_id} not found")

    try:
        mp3 = _download_preview(track["preview_url"])
    except OSError:
        # Deezer preview fetch failed -- flake, timeout, 404. urllib raises
        # OSError subclasses (URLError, socket.timeout included). Don't 500
        # on a transient failure; hand the job to the Mac embed worker.
        return _seed_via_worker(req.track_id, track)

    try:
        features = _to_plain(analyze_track(mp3))
        _safe(store.put_track, track, features)
    except (NotImplementedError, ImportError):
        # Analysis can't run on this host (no aarch64 essentia wheels on the
        # ARM VM). Hand the job to the Mac embed worker via Redis and wait.
        return _seed_via_worker(req.track_id, track)
    finally:
        mp3.unlink(missing_ok=True)
    return ready


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


class _CorpusMatrix(NamedTuple):
    corpus: tuple[str, ...]        # the corpus:ids snapshot this was built from
    ids: list[str]                 # the rows actually present, in row order
    matrix: np.ndarray
    correction: np.ndarray | None  # centrality, computed only if an axis wants it


# One assembled matrix per feature key, extended as the corpus grows.
# Every seed ranks against the same vectors, so reading and JSON-parsing each
# track's features per request was pure repetition -- 25 s at 7.8k tracks and
# linear from there. Parsing is the cost, not the round trip, so a cache that
# rebuilt whenever corpus:ids changed bought nothing while a crawl was running:
# it changes every few seconds. Only genuinely new ids are parsed and appended.
# Held in process: the corpus is numpy-sized, not database-sized.
_MATRIX_CACHE: dict[str, _CorpusMatrix] = {}
# Endpoints are sync, so FastAPI runs them on a threadpool: without this two
# concurrent requests would each build the matrix, and the first one to finish
# would be overwritten by the second.
_MATRIX_LOCK = threading.Lock()


def _rows_for(track_ids: list[str], feature_key: str) -> tuple[list[str], list[np.ndarray]]:
    """Fetch and vectorize a set of tracks, skipping any without this feature."""
    ids, rows = [], []
    for track_id, features in zip(track_ids, store.get_many_features(track_ids)):
        if features and feature_key in features:
            ids.append(track_id)
            rows.append(_vector(features, feature_key))
    return ids, rows


def _corpus_matrix(corpus: tuple[str, ...], feature_key: str, metric: str,
                   want_correction: bool) -> tuple[list[str], np.ndarray, np.ndarray | None]:
    """The corpus as one matrix, parsing only what it has not seen before."""
    with _MATRIX_LOCK:
        return _build(corpus, feature_key, metric, want_correction)


def _build(corpus: tuple[str, ...], feature_key: str, metric: str,
           want_correction: bool) -> tuple[list[str], np.ndarray, np.ndarray | None]:
    cached = _MATRIX_CACHE.get(feature_key)
    known = set(cached.ids) if cached else set()

    # Tracks only ever get added, so the common case is a short tail of new ids.
    # A track disappearing means someone cleared Redis: drop it all and rebuild.
    if cached is not None and not known.issubset(corpus):
        cached, known = None, set()

    fresh = [i for i in corpus if i not in known]
    if cached is None:
        ids, rows = _rows_for(list(corpus), feature_key)
        matrix = np.stack(rows) if rows else np.empty((0, 1))
        cached = _CorpusMatrix(corpus, ids, matrix, None)
    elif fresh:
        ids, rows = _rows_for(fresh, feature_key)
        if rows:
            cached = _CorpusMatrix(
                corpus, cached.ids + ids, np.vstack([cached.matrix, np.stack(rows)]),
                None,  # the corpus moved, so any cached centrality is stale
            )
        else:
            cached = cached._replace(corpus=corpus)
    _MATRIX_CACHE[feature_key] = cached

    if want_correction and cached.correction is None and len(cached.ids):
        from music_recommendations.server import rank as rank_mod

        # A property of the corpus rather than of the seed, so it is cached
        # beside it. It therefore includes the seed's own row, where the
        # pre-cache code excluded it -- one row in thousands, and it makes the
        # correction the same for every seed instead of subtly seed-dependent.
        cached = cached._replace(
            correction=rank_mod.centrality(cached.matrix, metric)
        )
        _MATRIX_CACHE[feature_key] = cached

    return cached.ids, cached.matrix, (cached.correction if want_correction else None)


@app.get("/recommend")
def recommend(track_id: str, axis: str,
              limit: int = Query(10, ge=1, le=50)) -> dict:
    if axis not in AXIS_FEATURES:
        raise HTTPException(400, f"unknown axis {axis!r}")

    feature_key, direction = AXIS_FEATURES[axis]
    seed_features = _safe(store.get_features, track_id)
    corpus = tuple(_safe(store.corpus_ids, default=[]))
    ranked_against = [i for i in corpus if i != track_id]

    if seed_features is None or not ranked_against:
        results = _fixture_fallback(track_id, limit)
    else:
        from music_recommendations.server import rank as rank_mod

        # The right metric depends on how the vector was built, so analysis
        # declares it per feature key rather than the server assuming cosine.
        metric = METRICS.get(feature_key, "cosine")
        ids, matrix, correction = _corpus_matrix(corpus, feature_key, metric,
                                                 want_correction=direction == -1)
        seed_vec = _vector(seed_features, feature_key)

        # The seed is a row in the cached matrix like any other, so ask for one
        # extra and drop it — cheaper than rebuilding the matrix per seed.
        order = rank_mod.rank(
            seed_vec, matrix, direction=direction, limit=limit + 1,
            metric=metric, correction=correction,
        )
        similarity = rank_mod.scores(seed_vec, matrix, metric)
        results = []
        for idx in order:
            if ids[idx] == track_id:
                continue
            track = store.get_track(ids[idx])
            results.append({**track, "score": float(similarity[idx])})
            if len(results) == limit:
                break

    return {"seed_track_id": track_id, "axis": axis, "results": results}


# ---- /viz/map — demo/debug, NOT part of contract/contract.md (like GET /) ----

# The 2D projection of the embedding matrix, kept beside the matrix it was
# computed from: recomputed only when _corpus_matrix hands back a new object
# (corpus grew or was rebuilt), served from memory otherwise.
_PROJECTION_CACHE: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _projection(matrix: np.ndarray) -> np.ndarray:
    cached = _PROJECTION_CACHE.get("embedding")
    if cached is not None and cached[0] is matrix:
        return cached[1]
    xy = viz.project_2d(matrix)
    _PROJECTION_CACHE["embedding"] = (matrix, xy)
    return xy


@app.get("/viz/map")
def viz_map(track_id: str, axis: str,
            limit: int = Query(10, ge=1, le=50)) -> dict:
    """Everything the wow screen needs in one payload: the whole corpus as 2D
    points, the seed, and the recs with the actual numbers behind each score."""
    if axis not in AXIS_FEATURES:
        raise HTTPException(400, f"unknown axis {axis!r}")

    feature_key, direction = AXIS_FEATURES[axis]
    seed_features = _safe(store.get_features, track_id)
    corpus = tuple(_safe(store.corpus_ids, default=[]))
    if seed_features is None or not corpus:
        raise HTTPException(404, f"track {track_id} not analyzed")

    # The map is always embedding space, whatever the axis scores with.
    emb_ids, emb_matrix, _ = _corpus_matrix(corpus, "embedding", "cosine",
                                            want_correction=False)
    if track_id not in emb_ids:
        raise HTTPException(404, f"track {track_id} not in corpus")
    xy = _projection(emb_matrix)
    position = {tid: i for i, tid in enumerate(emb_ids)}

    from music_recommendations.server import rank as rank_mod

    metric = METRICS.get(feature_key, "cosine")
    ids, matrix, correction = _corpus_matrix(corpus, feature_key, metric,
                                             want_correction=direction == -1)
    seed_vec = _vector(seed_features, feature_key)
    order = rank_mod.rank(seed_vec, matrix, direction=direction,
                          limit=limit + 1, metric=metric, correction=correction)
    similarity = rank_mod.scores(seed_vec, matrix, metric)

    recs = []
    for idx in order:
        rec_id = ids[idx]
        if rec_id == track_id or rec_id not in position:
            continue
        track = _safe(store.get_track, rec_id)
        features = _safe(store.get_features, rec_id, default={})
        pos = position[rec_id]
        recs.append({
            **(track or {"track_id": rec_id}),
            "score": float(similarity[idx]),
            "x": float(xy[pos, 0]),
            "y": float(xy[pos, 1]),
            "groove": (features or {}).get("groove"),
            "math": viz.score_math(
                seed_vec, matrix[idx], metric,
                float(correction[idx]) if correction is not None else None,
            ),
        })
        if len(recs) == limit:
            break

    seed_track = _safe(store.get_track, track_id) or {"track_id": track_id}
    seed_pos = position[track_id]
    seed = {
        **seed_track,
        "x": float(xy[seed_pos, 0]),
        "y": float(xy[seed_pos, 1]),
        "groove": seed_features.get("groove"),
    }

    return {
        "points": {
            "ids": emb_ids,
            "x": [round(float(v), 4) for v in xy[:, 0]],
            "y": [round(float(v), 4) for v in xy[:, 1]],
        },
        "seed": seed,
        "recs": recs,
        "axis": {"id": axis, "metric": metric, "direction": direction},
    }


def _fixture_fallback(track_id: str, limit: int) -> list[dict]:
    tracks = [t for t in _fixture_tracks() if t["track_id"] != track_id][:limit]
    return [
        {**t, "score": round(0.95 - 0.05 * i, 4)} for i, t in enumerate(tracks)
    ]


def _vector(features: dict, key: str) -> np.ndarray:
    value = features[key]
    return np.atleast_1d(np.asarray(value, dtype=float))


def _to_plain(features: dict) -> dict:
    """np arrays/scalars -> JSON-serializable lists/floats."""
    return {
        k: v.tolist() if hasattr(v, "tolist") else v for k, v in features.items()
    }
