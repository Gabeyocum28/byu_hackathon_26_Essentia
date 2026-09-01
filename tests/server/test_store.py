"""store.py: Redis key layout from the module docstring."""
from music_recommendations.server import store

TRACK = {
    "track_id": "42",
    "title": "Blue in Green",
    "artist": "Miles Davis",
    "album": "Kind of Blue",
    "artwork_url": "http://x/a.jpg",
    "preview_url": "http://x/p.mp3",
}
FEATURES = {"embedding": [0.1, 0.2], "genre": [0.7, 0.1, 0.2]}


def test_put_then_get_track_roundtrips(fake_redis):
    store.put_track(TRACK, FEATURES)
    assert store.get_track("42") == TRACK


def test_put_then_get_features_roundtrips(fake_redis):
    store.put_track(TRACK, FEATURES)
    assert store.get_features("42") == FEATURES


def test_put_registers_corpus_id(fake_redis):
    store.put_track(TRACK, FEATURES)
    assert store.corpus_ids() == ["42"]


def test_get_missing_track_returns_none(fake_redis):
    assert store.get_track("nope") is None
    assert store.get_features("nope") is None


def test_corpus_ids_empty_when_no_tracks(fake_redis):
    assert store.corpus_ids() == []
