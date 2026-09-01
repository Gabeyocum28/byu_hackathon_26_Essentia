"""viz.py + GET /viz/map: 2D projection of the corpus and per-rec score math.

Non-contract debug/demo endpoint. The galaxy map is always a projection of
EMBEDDING space (that's "where the music lies"); the axis only changes which
scores and math are attached to the recommendations.
"""
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from music_recommendations.server import app as app_module
from music_recommendations.server import store, viz

FIXTURE = json.loads(
    (Path(__file__).parents[2] / "contract" / "fixture.json").read_text()
)["tracks"]


# ---- project_2d (pure math) ----

def test_project_2d_shape_and_determinism():
    rng = np.random.default_rng(0)
    matrix = rng.normal(size=(30, 8))
    xy = viz.project_2d(matrix)
    assert xy.shape == (30, 2)
    assert np.allclose(xy, viz.project_2d(matrix))


def test_project_2d_first_axis_captures_dominant_direction():
    # Points spread 100x wider along one direction: that spread must land on x.
    rng = np.random.default_rng(1)
    matrix = rng.normal(size=(50, 5))
    matrix[:, 2] *= 100.0
    xy = viz.project_2d(matrix)
    assert xy[:, 0].std() > xy[:, 1].std()


def test_project_2d_handles_single_row():
    xy = viz.project_2d(np.ones((1, 4)))
    assert xy.shape == (1, 2)
    assert np.all(np.isfinite(xy))


# ---- GET /viz/map ----

def fake_features(i: int, n: int) -> dict:
    v = [0.0] * 1280
    v[0] = 1.0
    v[1] = i / max(n - 1, 1)
    v[2] = float(i % 3)
    return {"embedding": v, "groove": [120.0 + i, 0.9, 3.0, 0.5 + 0.01 * i]}


@pytest.fixture
def client(fake_redis):
    return TestClient(app_module.app)


@pytest.fixture
def seeded_corpus(fake_redis):
    tracks = FIXTURE[:8]
    for i, t in enumerate(tracks):
        store.put_track(t, fake_features(i, len(tracks)))
    return tracks


def test_viz_map_404_when_seed_unanalyzed(client, fake_redis):
    resp = client.get("/viz/map", params={"track_id": "nope", "axis": "sounds_like"})
    assert resp.status_code == 404


def test_viz_map_400_on_unknown_axis(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    resp = client.get("/viz/map", params={"track_id": tid, "axis": "vibes"})
    assert resp.status_code == 400


def test_viz_map_points_cover_corpus(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like", "limit": 3}
    ).json()
    points = body["points"]
    assert set(points) == {"ids", "x", "y", "tracks"}
    assert sorted(points["ids"]) == sorted(t["track_id"] for t in seeded_corpus)
    assert len(points["x"]) == len(points["y"]) == len(points["ids"])
    assert all(np.isfinite(points["x"])) and all(np.isfinite(points["y"]))


def test_viz_map_point_metadata_stays_aligned_with_coordinates(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    points = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like", "limit": 3}
    ).json()["points"]

    assert len(points["tracks"]) == len(points["ids"])
    assert [track["track_id"] for track in points["tracks"]] == points["ids"]
    assert all(track["title"] and track["artist"] for track in points["tracks"])


def test_viz_map_seed_has_position_and_groove(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like"}
    ).json()
    seed = body["seed"]
    assert seed["track_id"] == tid
    assert seed["title"] == seeded_corpus[0]["title"]
    assert isinstance(seed["x"], float) and isinstance(seed["y"], float)
    assert len(seed["groove"]) == 4


def test_viz_map_recs_match_recommend_scores(client, seeded_corpus):
    """The wow screen must show the SAME ranking the user just saw."""
    tid = seeded_corpus[0]["track_id"]
    rec_body = client.get(
        "/recommend", params={"track_id": tid, "axis": "sounds_like", "limit": 3}
    ).json()
    viz_body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like", "limit": 3}
    ).json()
    assert [r["track_id"] for r in viz_body["recs"]] == \
        [r["track_id"] for r in rec_body["results"]]
    for vr, rr in zip(viz_body["recs"], rec_body["results"]):
        assert vr["score"] == pytest.approx(rr["score"])


def test_viz_map_rec_math_reconstructs_cosine(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like", "limit": 3}
    ).json()
    assert body["axis"] == {"id": "sounds_like", "metric": "cosine", "direction": 1}
    for rec in body["recs"]:
        math = rec["math"]
        cosine = math["dot"] / (math["seed_norm"] * math["rec_norm"])
        assert cosine == pytest.approx(rec["score"])
        assert math["centrality"] is None
        assert len(rec["groove"]) == 4


def test_viz_map_surprise_includes_centrality(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "surprise", "limit": 3}
    ).json()
    assert body["axis"]["direction"] == -1
    for rec in body["recs"]:
        assert isinstance(rec["math"]["centrality"], float)


def test_viz_map_groove_axis_reports_euclidean(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "groove", "limit": 3}
    ).json()
    assert body["axis"]["metric"] == "euclidean"
    for rec in body["recs"]:
        # score = 1/(1+distance) must hold, so the panel can show the distance
        assert rec["math"]["distance"] is not None
        assert rec["score"] == pytest.approx(1.0 / (1.0 + rec["math"]["distance"]))
