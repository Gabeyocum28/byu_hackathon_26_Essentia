"""embed_worker.py: pop queued tracks, analyze locally, write back to Redis."""
import importlib.util
from pathlib import Path

import pytest

from music_recommendations.server import store

SCRIPT = Path(__file__).parents[2] / "scripts" / "embed_worker.py"
spec = importlib.util.spec_from_file_location("embed_worker", SCRIPT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

TRACK = {
    "track_id": "42",
    "title": "Blue in Green",
    "artist": "Miles Davis",
    "album": "Kind of Blue",
    "artwork_url": "http://x/a.jpg",
    "preview_url": "http://x/p.mp3",
}
FEATURES = {"embedding": [0.1, 0.2], "groove": [120.0, 0.9, 3.1, 0.5]}


@pytest.fixture
def analysis_ok(monkeypatch, tmp_path):
    mp3 = tmp_path / "p.mp3"
    mp3.write_bytes(b"mp3")
    monkeypatch.setattr(worker, "download_preview", lambda url: mp3)
    monkeypatch.setattr(worker, "analyze_track", lambda p: dict(FEATURES))


def test_process_job_analyzes_stores_and_clears_marker(fake_redis, analysis_ok):
    store.put_track_meta(TRACK)
    store.enqueue_embed("42")

    assert worker.process_job("42") is True
    assert store.get_features("42") == FEATURES
    assert "42" in store.corpus_ids()
    assert store.enqueue_embed("42") is True   # marker cleared -> re-enqueueable


def test_process_job_falls_back_to_deezer_for_metadata(fake_redis, analysis_ok, monkeypatch):
    monkeypatch.setattr(worker.deezer, "get_track", lambda t: dict(TRACK))
    assert worker.process_job("42") is True
    assert store.get_track("42") == TRACK


def test_process_job_failure_logs_clears_marker_never_raises(fake_redis, monkeypatch):
    def boom(url):
        raise OSError("download failed")

    store.put_track_meta(TRACK)
    store.enqueue_embed("42")
    monkeypatch.setattr(worker, "download_preview", boom)

    assert worker.process_job("42") is False
    assert store.get_features("42") is None
    assert store.enqueue_embed("42") is True   # marker cleared despite failure


def test_process_job_no_metadata_anywhere_fails_cleanly(fake_redis, monkeypatch):
    monkeypatch.setattr(worker.deezer, "get_track", lambda t: None)
    assert worker.process_job("42") is False


def test_tick_survives_a_dequeue_connection_error(monkeypatch):
    """A transient Redis error on the blocking pop must not kill the loop."""
    calls = {"n": 0}

    def flaky_dequeue(timeout=5):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("connection refused")
        return None

    monkeypatch.setattr(worker.store, "dequeue_embed", flaky_dequeue)
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)

    worker._tick()  # first call: dequeue raises, caught and swallowed
    assert calls["n"] == 1
    worker._tick()  # second call: process continues normally
    assert calls["n"] == 2
