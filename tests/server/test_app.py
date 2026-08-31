"""app.py: the four contract routes, mock-first with Redis + analysis real path."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from music_recommendations.server import app as app_module
from music_recommendations.server import store
from contract.features import AXES, FEATURE_KEYS

FIXTURE = json.loads(
    (Path(__file__).parents[2] / "contract" / "fixture.json").read_text()
)["tracks"]

TRACK_KEYS = {"track_id", "title", "artist", "album", "artwork_url", "preview_url"}


def fake_features(seed_val: float) -> dict:
    """Synthetic feature dict matching contract FEATURE_KEYS shapes."""
    out = {}
    for key, dim in FEATURE_KEYS.items():
        if dim == 1:
            out[key] = seed_val
        else:
            v = [0.0] * dim
            v[0] = 1.0
            v[1] = seed_val
            out[key] = v
    return out


@pytest.fixture
def client(fake_redis):
    return TestClient(app_module.app)


@pytest.fixture
def seeded_corpus(fake_redis):
    """Five analyzed tracks in the fake store, spread across feature space."""
    for i, t in enumerate(FIXTURE[:5]):
        store.put_track(t, fake_features(i / 4.0))
    return FIXTURE[:5]


# ---- /axes ----

def test_axes_serves_contract_list_verbatim(client):
    assert client.get("/axes").json() == {"axes": AXES}


# ---- /search ----

def test_search_proxies_deezer(client, monkeypatch):
    hits = [dict(FIXTURE[0])]
    monkeypatch.setattr(app_module.deezer, "search", lambda q, limit=10: hits)
    body = client.get("/search", params={"q": "so what"}).json()
    assert body == {"results": hits}


def test_search_falls_back_to_fixture_when_deezer_down(client, monkeypatch):
    def boom(q, limit=10):
        raise OSError("no network")

    monkeypatch.setattr(app_module.deezer, "search", boom)
    body = client.get("/search", params={"q": "miles"}).json()
    assert len(body["results"]) > 0
    assert all("miles" in t["artist"].lower() or "miles" in t["title"].lower()
               for t in body["results"])
    assert all(set(t) == TRACK_KEYS for t in body["results"])


# ---- /seed ----

def test_seed_warm_track_is_instant_and_never_analyzes(client, seeded_corpus, monkeypatch):
    def boom(path):
        raise AssertionError("analyze_track must not run for a warm seed")

    monkeypatch.setattr(app_module, "analyze_track", boom)
    tid = seeded_corpus[0]["track_id"]
    body = client.post("/seed", json={"track_id": tid}).json()
    assert body == {"track_id": tid, "status": "ready"}


def test_seed_cold_track_downloads_analyzes_and_stores(client, fake_redis, monkeypatch):
    track = dict(FIXTURE[7])
    tid = track["track_id"]
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(track))
    monkeypatch.setattr(app_module, "_download_preview", lambda url: Path("/tmp/x.mp3"))
    monkeypatch.setattr(app_module, "analyze_track", lambda p: fake_features(0.5))

    body = client.post("/seed", json={"track_id": tid}).json()
    assert body == {"track_id": tid, "status": "ready"}
    assert store.get_features(tid) is not None
    assert store.get_track(tid) == track


def test_seed_fixture_fallback_when_analysis_unavailable(client, fake_redis, monkeypatch):
    """Mock-first: analysis is a stub -> fixture tracks still seed as ready."""
    def not_implemented(path):
        raise NotImplementedError

    tid = FIXTURE[0]["track_id"]
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: dict(FIXTURE[0]))
    monkeypatch.setattr(app_module, "_download_preview", lambda url: Path("/tmp/x.mp3"))
    monkeypatch.setattr(app_module, "analyze_track", not_implemented)
    body = client.post("/seed", json={"track_id": tid})
    assert body.status_code == 200
    assert body.json()["status"] == "ready"


def test_seed_unknown_track_404(client, fake_redis, monkeypatch):
    monkeypatch.setattr(app_module.deezer, "get_track", lambda t: None)
    assert client.post("/seed", json={"track_id": "doesnotexist"}).status_code == 404


# ---- /recommend ----

def test_recommend_returns_scored_tracks_excluding_seed(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get("/recommend", params={"track_id": tid, "axis": "sounds_like"}).json()
    assert body["seed_track_id"] == tid
    assert body["axis"] == "sounds_like"
    ids = [t["track_id"] for t in body["results"]]
    assert tid not in ids
    assert len(ids) == 4
    for t in body["results"]:
        assert set(t) == TRACK_KEYS | {"score"}
        assert isinstance(t["score"], float)


def test_recommend_orders_by_similarity(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]  # seed_val 0.0; nearest is seed_val 0.25
    body = client.get("/recommend", params={"track_id": tid, "axis": "sounds_like"}).json()
    scores = [t["score"] for t in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert body["results"][0]["track_id"] == seeded_corpus[1]["track_id"]


def test_recommend_surprise_inverts_order(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    near = client.get("/recommend", params={"track_id": tid, "axis": "sounds_like"}).json()
    far = client.get("/recommend", params={"track_id": tid, "axis": "surprise"}).json()
    assert [t["track_id"] for t in far["results"]] == \
        [t["track_id"] for t in near["results"]][::-1]


def test_recommend_respects_limit(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    body = client.get(
        "/recommend", params={"track_id": tid, "axis": "sounds_like", "limit": 2}
    ).json()
    assert len(body["results"]) == 2


def test_recommend_unknown_axis_400(client, seeded_corpus):
    tid = seeded_corpus[0]["track_id"]
    r = client.get("/recommend", params={"track_id": tid, "axis": "vibes"})
    assert r.status_code == 400


def test_recommend_unseeded_track_falls_back_to_fixture(client, fake_redis):
    """Mock-first: empty corpus -> fixture tracks with dummy descending scores."""
    body = client.get(
        "/recommend", params={"track_id": FIXTURE[0]["track_id"], "axis": "groove"}
    ).json()
    ids = [t["track_id"] for t in body["results"]]
    assert len(ids) == 10
    assert FIXTURE[0]["track_id"] not in ids
    scores = [t["score"] for t in body["results"]]
    assert scores == sorted(scores, reverse=True)


# ---- no Redis at all (mock-first before anything lands) ----

@pytest.fixture
def no_redis(monkeypatch):
    class Down:
        def __getattr__(self, name):
            raise ConnectionError("redis is down")

    monkeypatch.setattr(store, "client", lambda: Down())


def test_seed_works_without_redis(no_redis, monkeypatch):
    client = TestClient(app_module.app)
    tid = FIXTURE[0]["track_id"]
    monkeypatch.setattr(app_module, "_download_preview", lambda url: Path("/tmp/x.mp3"))
    body = client.post("/seed", json={"track_id": tid})
    assert body.status_code == 200
    assert body.json()["status"] == "ready"


def test_recommend_works_without_redis(no_redis):
    client = TestClient(app_module.app)
    body = client.get(
        "/recommend", params={"track_id": FIXTURE[0]["track_id"], "axis": "mood"}
    )
    assert body.status_code == 200
    assert len(body.json()["results"]) == 10


# ---- / signpost ----

def test_root_lists_routes(client):
    body = client.get("/").json()
    assert "/axes" in str(body)
    assert "/recommend" in str(body)
