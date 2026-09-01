"""Shared fakes: an in-memory Redis standing in for the real one."""
import pytest

from music_recommendations.server import store


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.sets = {}

    def set(self, key, value):
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def mget(self, keys):
        return [self.kv.get(k) for k in keys]

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def smembers(self, key):
        return self.sets.get(key, set())


@pytest.fixture(autouse=True)
def clear_matrix_cache():
    """/recommend caches the corpus matrix in module state; tests must not share it."""
    from music_recommendations.server import app

    app._MATRIX_CACHE.clear()
    yield
    app._MATRIX_CACHE.clear()


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(store, "client", lambda: fake)
    return fake
