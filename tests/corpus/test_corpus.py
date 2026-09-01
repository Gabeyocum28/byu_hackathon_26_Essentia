"""corpus/: shape conversion, dedup, versioning. No network in these tests."""
import importlib.util
from pathlib import Path

import pytest

from music_recommendations.corpus import deezer, ingest

CONTRACT = Path(__file__).resolve().parents[2] / "contract"


def _track_fields():
    spec = importlib.util.spec_from_file_location("features", CONTRACT / "features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TRACK_FIELDS


RAW = {
    "id": 2711778,
    "title": "So What",
    "preview": "https://cdnt-preview.dzcdn.net/x.mp3",
    "artist": {"name": "Miles Davis"},
    "album": {"title": "Kind Of Blue", "cover_medium": "https://img/250.jpg"},
}


def test_track_to_contract_produces_exactly_the_contract_fields():
    track = deezer.track_to_contract(RAW)
    assert set(track) == _track_fields()
    assert track["track_id"] == "2711778"
    assert isinstance(track["track_id"], str), "track_id is a string everywhere"


def test_track_without_preview_is_dropped():
    """A track we cannot play is useless to the app and to analysis."""
    assert deezer.track_to_contract({**RAW, "preview": ""}) is None
    assert deezer.track_to_contract({k: v for k, v in RAW.items() if k != "preview"}) is None


def test_missing_album_or_artist_does_not_crash():
    """Deezer omits these on some payloads; a crawl must not die on one row."""
    track = deezer.track_to_contract({"id": 1, "title": "x", "preview": "http://a"})
    assert set(track) == _track_fields()
    assert track["artist"] == "" and track["album"] == ""


def test_already_stored_is_false_when_redis_is_unreachable(monkeypatch):
    """A crawl against a dead Redis should re-do work, not silently skip it."""
    def boom(_track_id):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(ingest.store, "get_features", boom)
    assert ingest.already_stored("123") is False


def test_already_stored_rejects_a_stale_feature_version(monkeypatch):
    current = ingest.FEATURES_VERSION
    monkeypatch.setattr(
        ingest.store, "get_features",
        lambda _t: {"embedding": [0.0], ingest.VERSION_KEY: current - 1},
    )
    assert ingest.already_stored("123") is False

    monkeypatch.setattr(
        ingest.store, "get_features",
        lambda _t: {"embedding": [0.0], ingest.VERSION_KEY: current},
    )
    assert ingest.already_stored("123") is True


def test_already_stored_rejects_features_written_before_versioning(monkeypatch):
    monkeypatch.setattr(ingest.store, "get_features", lambda _t: {"embedding": [0.0]})
    assert ingest.already_stored("123") is False


@pytest.mark.parametrize("shards", [2, 3, 5])
def test_sharding_covers_every_track_exactly_once(shards):
    """Two machines must not collide and must not leave gaps."""
    ids = [str(i) for i in range(1000, 1200)]
    seen = []
    for index in range(shards):
        seen += [i for i in ids if int(i) % shards == index]
    assert sorted(seen) == sorted(ids)
    assert len(seen) == len(set(seen))
