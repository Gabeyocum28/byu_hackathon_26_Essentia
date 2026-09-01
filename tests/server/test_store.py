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


def test_get_many_tracks_preserves_requested_order_and_missing_values(fake_redis):
    store.put_track(TRACK, FEATURES)

    assert store.get_many_tracks(["nope", "42", "also-nope"]) == [
        None,
        TRACK,
        None,
    ]


def test_corpus_ids_empty_when_no_tracks(fake_redis):
    assert store.corpus_ids() == []


# ---- embed queue ----

def test_put_track_meta_writes_track_only(fake_redis):
    track = {"track_id": "9", "title": "T", "artist": "A", "album": "B",
             "artwork_url": "u", "preview_url": "p"}
    store.put_track_meta(track)
    assert store.get_track("9") == track
    assert store.get_features("9") is None
    assert "9" not in store.corpus_ids()


def test_enqueue_embed_pushes_and_guards(fake_redis):
    assert store.enqueue_embed("9") is True
    assert store.enqueue_embed("9") is False          # dedup guard holds
    assert fake_redis.lists["embed:queue"] == ["9"]


def test_enqueue_embed_repushes_after_ttl_expiry(fake_redis):
    store.enqueue_embed("9")
    fake_redis.delete("embed:queued:9")               # simulate TTL expiry
    assert store.enqueue_embed("9") is True
    assert fake_redis.lists["embed:queue"] == ["9", "9"]


def test_dequeue_embed_pops_oldest_then_none(fake_redis):
    store.enqueue_embed("1")
    store.enqueue_embed("2")
    assert store.dequeue_embed(timeout=1) == "1"
    assert store.dequeue_embed(timeout=1) == "2"
    assert store.dequeue_embed(timeout=1) is None


def test_clear_embed_marker_allows_reenqueue(fake_redis):
    store.enqueue_embed("9")
    store.clear_embed_marker("9")
    assert store.enqueue_embed("9") is True
