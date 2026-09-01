"""viz.py + GET /viz/map: 2D projection of the corpus and per-rec score math.

Non-contract debug/demo endpoint. The galaxy map is always a projection of
EMBEDDING space (that's "where the music lies"); the axis only changes which
scores and math are attached to the recommendations.
"""
import base64
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


# ---- project_top8 (pure math) ----

def test_project_top8_shape_and_determinism():
    rng = np.random.default_rng(0)
    matrix = rng.normal(size=(30, 10))
    coords8, variance = viz.project_top8(matrix)
    assert coords8.shape == (30, 8)
    assert variance.shape == (8,)
    coords8_again, variance_again = viz.project_top8(matrix)
    assert np.allclose(coords8, coords8_again)
    assert np.allclose(variance, variance_again)


def test_project_top8_matches_project_2d_first_two_columns():
    rng = np.random.default_rng(2)
    matrix = rng.normal(size=(25, 6))
    xy = viz.project_2d(matrix)
    coords8, _ = viz.project_top8(matrix)
    assert np.allclose(xy, coords8[:, :2])


def test_project_top8_variance_non_increasing_and_bounded():
    rng = np.random.default_rng(3)
    matrix = rng.normal(size=(40, 12))
    _, variance = viz.project_top8(matrix)
    assert np.all(variance >= 0.0) and np.all(variance <= 1.0)
    assert all(variance[i] >= variance[i + 1] for i in range(7))


def test_project_top8_pads_low_dimensional_corpora():
    rng = np.random.default_rng(4)
    matrix = rng.normal(size=(6, 3))
    coords8, variance = viz.project_top8(matrix)
    assert coords8.shape == (6, 8)
    assert np.allclose(coords8[:, 3:], 0.0)
    assert np.allclose(variance[3:], 0.0)


def test_project_top8_handles_single_row():
    coords8, variance = viz.project_top8(np.ones((1, 4)))
    assert coords8.shape == (1, 8)
    assert variance.shape == (8,)
    assert np.all(np.isfinite(coords8))


# ---- minimum_spanning_tree (pure math) ----

def test_minimum_spanning_tree_known_by_inspection():
    # Four points on a line: 0, 1, 3, 6. Cosine distance won't reproduce a
    # literal line, so build a matrix whose cosine geometry has an obvious
    # MST instead: unit vectors at increasing angles on a quarter circle,
    # so the cheapest tree is the path 0-1-2-3 (each hop the same, adjacent
    # angle).
    theta = np.array([0.0, 0.2, 0.4, 0.6])
    matrix = np.column_stack([np.cos(theta), np.sin(theta)])
    edges = viz.minimum_spanning_tree(matrix)

    assert len(edges) == 3
    assert {(i, j) for i, j, _ in edges} == {(0, 1), (1, 2), (2, 3)}
    ds = [d for _, _, d in edges]
    assert ds == sorted(ds)


def test_minimum_spanning_tree_forms_spanning_tree():
    rng = np.random.default_rng(5)
    matrix = rng.normal(size=(20, 5))
    ids, matrix = list(range(20)), matrix
    edges = viz.minimum_spanning_tree(matrix)
    assert len(edges) == len(ids) - 1

    parent = list(range(len(ids)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    components = len(ids)
    for i, j, _ in edges:
        assert i < j
        ri, rj = find(i), find(j)
        assert ri != rj  # no cycle
        parent[ri] = rj
        components -= 1
    assert components == 1


def test_minimum_spanning_tree_sorted_ascending_and_deterministic():
    rng = np.random.default_rng(6)
    matrix = rng.normal(size=(15, 4))
    edges = viz.minimum_spanning_tree(matrix)
    ds = [d for _, _, d in edges]
    assert ds == sorted(ds)
    assert edges == viz.minimum_spanning_tree(matrix)


def test_minimum_spanning_tree_empty_for_single_row():
    assert viz.minimum_spanning_tree(np.ones((1, 4))) == []


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


def test_viz_map_reads_all_point_metadata_in_one_bulk_request(
    client, seeded_corpus, fake_redis
):
    tid = seeded_corpus[0]["track_id"]
    client.get("/viz/map", params={"track_id": tid, "axis": "sounds_like"})

    track_reads = [keys for keys in fake_redis.mget_calls if keys[0].startswith("track:")]
    assert len(track_reads) == 1
    assert len(track_reads[0]) == len(seeded_corpus)


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


def test_viz_map_can_disable_surprise_correction(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/viz/map",
        params={"track_id": tid, "axis": "surprise", "correction": "off"},
    ).json()
    assert body["axis"]["correction"] == "off"
    assert all(rec["math"]["centrality"] is None for rec in body["recs"])


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


# ---- T1: walk, histogram, and hubs ----

def test_shortest_walk_uses_knn_edges_and_preserves_endpoints():
    # Points on a quarter circle: the graph walk follows adjacent samples and
    # is longer than the direct chord through empty ambient space.
    theta = np.linspace(0, np.pi / 2, 7)
    matrix = np.column_stack([np.cos(theta), np.sin(theta)])

    path, geodesic, ambient = viz.shortest_walk(matrix, 0, 6, k=2)

    assert path[0] == 0 and path[-1] == 6
    assert len(path) > 2
    expected_ambient = 1.0 - float(matrix[0] @ matrix[6])
    assert geodesic > 0
    assert ambient == pytest.approx(expected_ambient)


def test_shortest_walk_graph_cache_pins_matrix_and_evicts_on_new_matrix():
    # The graph cache must hold the matrix it was built from: a bare id()
    # key let a freed matrix's address be reused by a successor, silently
    # serving stale node indices after the corpus grew mid-session.
    theta = np.linspace(0, np.pi / 2, 7)
    first = np.column_stack([np.cos(theta), np.sin(theta)])
    viz.shortest_walk(first, 0, 6, k=2)
    assert viz._GRAPH_CACHE is not None and viz._GRAPH_CACHE[0] is first

    second = np.column_stack([np.cos(theta[:5]), np.sin(theta[:5])])
    path, _, _ = viz.shortest_walk(second, 0, 4, k=2)
    assert viz._GRAPH_CACHE[0] is second
    assert max(path) < len(second)


def test_viz_walk_returns_track_path_and_distance_math(client, seeded_corpus):
    start = seeded_corpus[0]["track_id"]
    end = seeded_corpus[-1]["track_id"]
    response = client.get(
        "/viz/walk", params={"from": start, "to": end, "k": 3}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["path"][0]["track_id"] == start
    assert body["path"][-1]["track_id"] == end
    assert all("x" in step and "y" in step for step in body["path"])
    assert body["geodesic"] > 0
    assert body["ambient"] > 0
    assert body["detour"] == pytest.approx(body["geodesic"] / body["ambient"])


def test_viz_walk_rejects_unknown_endpoint(client, seeded_corpus):
    response = client.get(
        "/viz/walk",
        params={"from": seeded_corpus[0]["track_id"], "to": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "track missing not in corpus"


def test_viz_histogram_has_sixty_bins_and_analytic_null(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get("/viz/histogram", params={"track_id": tid}).json()

    assert len(body["bins"]) == len(body["counts"]) == 60
    assert sum(body["counts"]) == len(seeded_corpus) - 1
    assert body["null"]["mean"] == 0
    assert body["null"]["sd"] == pytest.approx(1 / np.sqrt(1280))
    assert body["rec_scores"] == sorted(body["rec_scores"], reverse=True)
    assert 0 <= body["percentile"] <= 100


def test_viz_histogram_404_when_track_missing(client, seeded_corpus):
    response = client.get(
        "/viz/histogram", params={"track_id": "missing"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "track missing not analyzed"


def test_viz_hubs_reports_k_occurrence_central_and_isolated(client, seeded_corpus):
    body = client.get("/viz/hubs", params={"k": 3, "limit": 3}).json()

    assert body["expected_k"] == 3
    assert sum(row["count"] for row in body["all_counts"]) == len(seeded_corpus) * 3
    assert len(body["hubs"]) == len(body["central"]) == len(body["isolated"]) == 3
    assert body["hubs"][0]["count"] >= body["hubs"][-1]["count"]
    assert body["central"][0]["centrality"] >= body["central"][-1]["centrality"]
    assert body["isolated"][0]["centrality"] <= body["isolated"][-1]["centrality"]


# ---- T2: tour, mst, extremes ----

def test_viz_tour_ids_and_coords_shape(client, seeded_corpus):
    body = client.get("/viz/tour").json()
    n = len(seeded_corpus)
    assert sorted(body["ids"]) == sorted(t["track_id"] for t in seeded_corpus)

    raw = base64.b64decode(body["coords8"])
    coords = np.frombuffer(raw, dtype="<f4").reshape(n, 8)
    assert coords.shape == (n, 8)
    assert np.all(np.isfinite(coords))

    assert len(body["variance"]) == 8
    for v in body["variance"]:
        assert 0.0 <= v <= 1.0
    assert all(
        body["variance"][i] >= body["variance"][i + 1] for i in range(7)
    )


def test_viz_tour_first_two_coords_match_viz_map_xy(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    map_body = client.get(
        "/viz/map", params={"track_id": tid, "axis": "sounds_like"}
    ).json()
    tour_body = client.get("/viz/tour").json()

    map_ids = map_body["points"]["ids"]
    tour_ids = tour_body["ids"]
    n = len(tour_ids)
    coords = np.frombuffer(
        base64.b64decode(tour_body["coords8"]), dtype="<f4"
    ).reshape(n, 8)

    tour_pos = {t: i for i, t in enumerate(tour_ids)}
    for i, mid in enumerate(map_ids):
        row = coords[tour_pos[mid]]
        assert row[0] == pytest.approx(map_body["points"]["x"][i], abs=1e-3)
        assert row[1] == pytest.approx(map_body["points"]["y"][i], abs=1e-3)


def test_viz_tour_is_deterministic_across_calls(client, seeded_corpus):
    first = client.get("/viz/tour").json()
    second = client.get("/viz/tour").json()
    assert first == second


def test_viz_tour_404_when_corpus_empty(client, fake_redis):
    resp = client.get("/viz/tour")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "needs at least two tracks"


def test_viz_mst_has_n_minus_one_edges_sorted_and_spanning(client, seeded_corpus):
    body = client.get("/viz/mst").json()
    ids = body["ids"]
    n = len(ids)
    edges = body["edges"]
    assert len(edges) == n - 1

    ds = [e[2] for e in edges]
    assert ds == sorted(ds)

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    components = n
    for i, j, d in edges:
        assert 0 <= i < n and 0 <= j < n and i < j
        ri, rj = find(i), find(j)
        assert ri != rj  # no cycle
        parent[ri] = rj
        components -= 1
    assert components == 1


def test_viz_mst_is_deterministic_across_calls(client, seeded_corpus):
    first = client.get("/viz/mst").json()
    second = client.get("/viz/mst").json()
    assert first == second


def test_viz_mst_404_when_corpus_empty(client, fake_redis):
    resp = client.get("/viz/mst")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "needs at least two tracks"


def test_viz_extremes_low_high_disjoint_and_ordered(client, seeded_corpus):
    body = client.get("/viz/extremes", params={"pc": 1, "limit": 3}).json()
    assert body["pc"] == 1
    assert 0.0 < body["variance_pct"] <= 100.0

    low_ids = [t["track_id"] for t in body["low"]]
    high_ids = [t["track_id"] for t in body["high"]]
    assert set(low_ids).isdisjoint(high_ids)

    tour = client.get("/viz/tour").json()
    n = len(tour["ids"])
    coords = np.frombuffer(
        base64.b64decode(tour["coords8"]), dtype="<f4"
    ).reshape(n, 8)
    pos = {t: i for i, t in enumerate(tour["ids"])}
    low_values = [coords[pos[i], 0] for i in low_ids]
    high_values = [coords[pos[i], 0] for i in high_ids]
    assert low_values == sorted(low_values)
    assert high_values == sorted(high_values, reverse=True)


def test_viz_extremes_pc2_differs_from_pc1(client, seeded_corpus):
    pc1 = client.get("/viz/extremes", params={"pc": 1}).json()
    pc2 = client.get("/viz/extremes", params={"pc": 2}).json()
    assert pc1["low"] != pc2["low"] or pc1["high"] != pc2["high"]


def test_viz_extremes_track_shape_matches_contract(client, seeded_corpus):
    body = client.get("/viz/extremes", params={"pc": 1, "limit": 2}).json()
    for track in body["low"] + body["high"]:
        assert set(track) >= {
            "track_id", "title", "artist", "album", "artwork_url", "preview_url",
        }


def test_viz_extremes_422_on_pc_out_of_range(client, seeded_corpus):
    assert client.get("/viz/extremes", params={"pc": 0}).status_code == 422
    assert client.get("/viz/extremes", params={"pc": 9}).status_code == 422


def test_viz_extremes_422_on_limit_out_of_range(client, seeded_corpus):
    assert client.get("/viz/extremes", params={"limit": 0}).status_code == 422
    assert client.get("/viz/extremes", params={"limit": 11}).status_code == 422


def test_viz_extremes_404_when_corpus_empty(client, fake_redis):
    resp = client.get("/viz/extremes")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "needs at least two tracks"
