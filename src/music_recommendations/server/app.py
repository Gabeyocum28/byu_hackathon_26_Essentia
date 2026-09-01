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
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from contract.features import AXES
from music_recommendations.analysis import analyze_track
from music_recommendations.analysis.schema import METRICS
from music_recommendations.server import deezer, store
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
    path = Path(tempfile.mkstemp(suffix=".mp3")[1])
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
        features = _to_plain(analyze_track(mp3))
        _safe(store.put_track, track, features)
    except (NotImplementedError, ImportError):
        # Analysis unavailable — stub not landed, or essentia can't import on
        # this host (no aarch64 wheels on the ARM VM). Mock-first: the seed is
        # "ready" and /recommend serves its fixture fallback.
        pass
    return ready


@app.get("/recommend")
def recommend(track_id: str, axis: str, limit: int = 10) -> dict:
    if axis not in AXIS_FEATURES:
        raise HTTPException(400, f"unknown axis {axis!r}")

    feature_key, direction = AXIS_FEATURES[axis]
    seed_features = _safe(store.get_features, track_id)
    candidate_ids = [
        i for i in _safe(store.corpus_ids, default=[]) if i != track_id
    ]

    if seed_features is None or not candidate_ids:
        results = _fixture_fallback(track_id, limit)
    else:
        seed_vec = _vector(seed_features, feature_key)
        matrix = np.stack(
            [_vector(store.get_features(i), feature_key) for i in candidate_ids]
        )
        from music_recommendations.server import rank as rank_mod

        # The right metric depends on how the vector was built, so analysis
        # declares it per feature key rather than the server assuming cosine.
        metric = METRICS.get(feature_key, "cosine")
        order = rank_mod.rank(
            seed_vec, matrix, direction=direction, limit=limit, metric=metric
        )
        similarity = rank_mod.scores(seed_vec, matrix, metric)
        results = []
        for idx in order:
            track = store.get_track(candidate_ids[idx])
            results.append({**track, "score": float(similarity[idx])})

    return {"seed_track_id": track_id, "axis": axis, "results": results}


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
