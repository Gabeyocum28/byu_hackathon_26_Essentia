"""FastAPI app. Routes mirror contract/contract.md exactly. Mock-first: serve
contract/fixture.json until the corpus lands.

Routes:
  GET  /search      -- query Deezer (or fixture fallback) for tracks
  POST /seed         -- mark a track as the seed for recommendations
  GET  /axes         -- list available recommendation axes
  GET  /recommend    -- ranked, scored tracks for a seed + axis
"""
from __future__ import annotations

import base64
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
from typing import Literal, NamedTuple

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

# The top-8 PC projection of the embedding matrix, kept beside the matrix it
# was computed from: recomputed only when _corpus_matrix hands back a new
# object (corpus grew or was rebuilt), served from memory otherwise. One SVD
# serves /viz/map + /viz/walk (columns 0:2) and /viz/tour + /viz/extremes
# (all 8 columns) — matrix-identity-pinned like _PAIRWISE_CACHE/_GRAPH_CACHE
# in viz.py (never key by bare id(matrix): a freed array's address can be
# reused by a later, differently-sized corpus).
_TOP8_CACHE: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

# The MST edge list of the embedding matrix, matrix-identity-pinned the same
# way. Not part of contract/contract.md — see /viz/mst below.
_MST_CACHE: dict[str, tuple[np.ndarray, list[tuple[int, int, float]]]] = {}


def _top8(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cached = _TOP8_CACHE.get("embedding")
    if cached is not None and cached[0] is matrix:
        return cached[1], cached[2]
    coords8, variance = viz.project_top8(matrix)
    _TOP8_CACHE["embedding"] = (matrix, coords8, variance)
    return coords8, variance


def _projection(matrix: np.ndarray) -> np.ndarray:
    """First two PC columns — numerically identical to viz.project_2d's
    output, since /viz/map's xy must not change when this cache was added."""
    coords8, _ = _top8(matrix)
    return coords8[:, :2]


def _mst(matrix: np.ndarray) -> list[tuple[int, int, float]]:
    cached = _MST_CACHE.get("embedding")
    if cached is not None and cached[0] is matrix:
        return cached[1]
    edges = viz.minimum_spanning_tree(matrix)
    _MST_CACHE["embedding"] = (matrix, edges)
    return edges


@app.get("/viz/map")
def viz_map(track_id: str, axis: str,
            limit: int = Query(10, ge=1, le=50),
            correction: Literal["on", "off"] = "on") -> dict:
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
    use_correction = direction == -1 and correction == "on"
    ids, matrix, correction = _corpus_matrix(corpus, feature_key, metric,
                                             want_correction=use_correction)
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
    point_tracks = []
    for point_id, track in zip(emb_ids, _safe(store.get_many_tracks, emb_ids,
                                                default=[])):
        point_tracks.append(track or {
            "track_id": point_id,
            "title": point_id,
            "artist": "Unknown artist",
            "album": "",
            "artwork_url": None,
            "preview_url": None,
        })
    axis_info = {"id": axis, "metric": metric, "direction": direction}
    if direction == -1:
        axis_info["correction"] = "on" if use_correction else "off"

    return {
        "points": {
            "ids": emb_ids,
            "x": [round(float(v), 4) for v in xy[:, 0]],
            "y": [round(float(v), 4) for v in xy[:, 1]],
            "tracks": point_tracks,
        },
        "seed": seed,
        "recs": recs,
        "axis": axis_info,
    }


def _viz_embedding_corpus() -> tuple[list[str], np.ndarray]:
    corpus = tuple(_safe(store.corpus_ids, default=[]))
    if not corpus:
        raise HTTPException(404, "analyzed corpus is empty")
    ids, matrix, _ = _corpus_matrix(
        corpus, "embedding", "cosine", want_correction=False
    )
    if not ids:
        raise HTTPException(404, "analyzed corpus is empty")
    return ids, matrix


def _viz_embedding_corpus_min2() -> tuple[list[str], np.ndarray]:
    """Like _viz_embedding_corpus, but the T2 endpoints (/viz/tour,
    /viz/mst, /viz/extremes) are pinned to a single 404 message regardless
    of whether the corpus is empty or has exactly one track -- SVD/MST need
    at least two rows either way."""
    try:
        ids, matrix = _viz_embedding_corpus()
    except HTTPException:
        ids, matrix = [], np.empty((0, 1))
    if len(ids) < 2:
        raise HTTPException(404, "needs at least two tracks")
    return ids, matrix


def _viz_track(track_id: str) -> dict:
    return _safe(store.get_track, track_id) or {
        "track_id": track_id,
        "title": track_id,
        "artist": "Unknown artist",
        "album": "",
        "artwork_url": None,
        "preview_url": None,
    }


@app.get("/viz/walk")
def viz_walk(from_: str = Query(alias="from"), to: str = Query(),
             k: int = Query(8, ge=1, le=50)) -> dict:
    ids, matrix = _viz_embedding_corpus()
    position = {track_id: index for index, track_id in enumerate(ids)}
    for endpoint in (from_, to):
        if endpoint not in position:
            raise HTTPException(404, f"track {endpoint} not in corpus")

    try:
        path, geodesic, ambient = viz.shortest_walk(
            matrix, position[from_], position[to], k=k
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    xy = _projection(matrix)
    steps = [
        {
            **_viz_track(ids[index]),
            "x": float(xy[index, 0]),
            "y": float(xy[index, 1]),
        }
        for index in path
    ]
    return {
        "path": steps,
        "geodesic": geodesic,
        "ambient": ambient,
        "detour": geodesic / ambient if ambient > 0 else 1.0,
        "k": min(k, len(ids) - 1),
    }


@app.get("/viz/histogram")
def viz_histogram(track_id: str) -> dict:
    seed_features = _safe(store.get_features, track_id)
    if not seed_features or "embedding" not in seed_features:
        raise HTTPException(404, f"track {track_id} not analyzed")
    ids, matrix = _viz_embedding_corpus()
    if track_id not in ids:
        raise HTTPException(404, f"track {track_id} not analyzed")

    from music_recommendations.server import rank as rank_mod

    similarities = rank_mod.scores(
        _vector(seed_features, "embedding"), matrix, "cosine"
    )
    values = np.delete(similarities, ids.index(track_id))
    counts, edges = np.histogram(values, bins=60, range=(-1.0, 1.0))
    centers = (edges[:-1] + edges[1:]) / 2
    rec_scores = np.sort(values)[::-1][:10]
    threshold = float(rec_scores[-1]) if len(rec_scores) else 0.0
    percentile = float(100.0 * np.mean(values <= threshold)) if len(values) else 0.0
    dimension = int(matrix.shape[1])
    return {
        "bins": [float(value) for value in centers],
        "counts": [int(value) for value in counts],
        "rec_scores": [float(value) for value in rec_scores],
        "percentile": percentile,
        "null": {"mean": 0.0, "sd": float(1.0 / np.sqrt(dimension))},
        "corpus": {
            "mean": float(values.mean()) if len(values) else 0.0,
            "sd": float(values.std()) if len(values) else 0.0,
        },
    }


@app.get("/viz/hubs")
def viz_hubs(k: int = Query(8, ge=1, le=50),
             limit: int = Query(5, ge=1, le=20)) -> dict:
    ids, matrix = _viz_embedding_corpus()
    if len(ids) < 2:
        raise HTTPException(404, "hubness needs at least two tracks")
    neighbor_k = min(k, len(ids) - 1)
    similarity = viz.pairwise_cosine(matrix)
    without_self = similarity.copy()
    np.fill_diagonal(without_self, -np.inf)
    neighbors = np.argpartition(
        -without_self, neighbor_k - 1, axis=1
    )[:, :neighbor_k]
    counts = np.bincount(neighbors.ravel(), minlength=len(ids))
    centrality = (similarity.sum(axis=1) - np.diag(similarity)) / (len(ids) - 1)

    index = np.arange(len(ids))
    hub_order = np.lexsort((index, -counts))
    central_order = np.lexsort((index, -centrality))
    isolated_order = np.lexsort((index, centrality))

    def rows(order: np.ndarray, field: str, values: np.ndarray) -> list[dict]:
        return [
            {**_viz_track(ids[i]), field: float(values[i])}
            for i in order[:limit]
        ]

    return {
        "hubs": [
            {**_viz_track(ids[i]), "count": int(counts[i])}
            for i in hub_order[:limit]
        ],
        "central": rows(central_order, "centrality", centrality),
        "isolated": rows(isolated_order, "centrality", centrality),
        "expected_k": neighbor_k,
        "all_counts": [
            {"track_id": track_id, "count": int(count)}
            for track_id, count in zip(ids, counts)
        ],
    }


@app.get("/viz/tour")
def viz_tour() -> dict:
    """Per-track top-8 PC coordinates + variance explained (T2.1).

    Non-contract debug/demo endpoint, like /viz/map and /viz/hubs. Columns
    0-1 of coords8 are numerically identical to /viz/map's x/y — same SVD,
    same sign convention, same matrix-pinned cache (_TOP8_CACHE).
    """
    ids, matrix = _viz_embedding_corpus_min2()
    coords8, variance = _top8(matrix)
    coords8_b64 = base64.b64encode(
        np.asarray(coords8, dtype="<f4").tobytes()
    ).decode("ascii")
    return {
        "ids": ids,
        "coords8": coords8_b64,
        "variance": [float(v) for v in variance],
    }


@app.get("/viz/mst")
def viz_mst() -> dict:
    """The n-1 MST edges over cosine distance — Prim in numpy (T2.2).

    Non-contract debug/demo endpoint. The H0 barcode's death times are
    exactly these edge weights.
    """
    ids, matrix = _viz_embedding_corpus_min2()
    edges = _mst(matrix)
    return {"ids": ids, "edges": [[i, j, d] for i, j, d in edges]}


@app.get("/viz/extremes")
def viz_extremes(pc: int = Query(1, ge=1, le=8),
                 limit: int = Query(4, ge=1, le=10)) -> dict:
    """Top/bottom tracks along one principal component (T2.4).

    Non-contract debug/demo endpoint. Reuses /viz/tour's top-8 PC cache.
    """
    ids, matrix = _viz_embedding_corpus_min2()
    coords8, variance = _top8(matrix)
    col = pc - 1
    values = coords8[:, col]

    k = min(limit, len(ids))
    low_order = np.argsort(values, kind="stable")          # most negative first
    high_order = np.argsort(-values, kind="stable")         # most positive first

    return {
        "pc": pc,
        "variance_pct": float(variance[col] * 100.0),
        "low": [_viz_track(ids[i]) for i in low_order[:k]],
        "high": [_viz_track(ids[i]) for i in high_order[:k]],
    }


@app.get("/viz/attribute")
def viz_attribute(seed: str, rec: str) -> dict:
    """Which frequency bands carry this pair's similarity (T2.6).

    Non-contract debug/demo endpoint, and the only /viz route that can't
    answer from the matrix alone: the counterfactual has to go back through
    the real model, which lives on the Mac worker. So this route is a
    mailbox — it serves the cached answer, or queues the pair and says
    "pending" while the worker band-stops, re-embeds, and writes the result.
    """
    if seed == rec:
        raise HTTPException(400, "seed and rec must differ")

    ids, _ = _viz_embedding_corpus()
    present = set(ids)
    for track_id in (seed, rec):
        if track_id not in present:
            raise HTTPException(404, f"track {track_id} not analyzed")

    cached = _safe(store.get_attribution, seed, rec)
    if cached:
        return cached

    _safe(store.enqueue_attribution, seed, rec)
    return {"status": "pending"}


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
