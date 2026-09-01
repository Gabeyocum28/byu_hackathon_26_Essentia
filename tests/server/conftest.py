"""Shared fakes: an in-memory Redis standing in for the real one."""
import pytest

from music_recommendations.server import store


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.sets = {}
        self.lists = {}
        self.mget_calls = []

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def mget(self, keys):
        self.mget_calls.append(keys)
        return [self.kv.get(k) for k in keys]

    def exists(self, key):
        return 1 if key in self.kv else 0

    def delete(self, key):
        self.kv.pop(key, None)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def srem(self, key, *values):
        self.sets.get(key, set()).difference_update(values)

    def sismember(self, key, value):
        return value in self.sets.get(key, set())

    def smembers(self, key):
        return self.sets.get(key, set())

    def lpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)

    def brpop(self, key, timeout=0):
        # Real BRPOP takes one key or several and answers from the first
        # non-empty one in order — that ordering is how the worker gives
        # embed jobs priority over attribution jobs.
        for name in ([key] if isinstance(key, str) else list(key)):
            items = self.lists.get(name)
            if items:
                return (name, items.pop(0))
        return None


@pytest.fixture(autouse=True)
def clear_matrix_cache():
    """/recommend caches the corpus matrix in module state; tests must not share it."""
    from music_recommendations.server import app, viz

    app._MATRIX_CACHE.clear()
    app._TOP8_CACHE.clear()
    app._MST_CACHE.clear()
    viz.clear_geometry_cache()
    yield
    app._MATRIX_CACHE.clear()
    app._TOP8_CACHE.clear()
    app._MST_CACHE.clear()
    viz.clear_geometry_cache()


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(store, "client", lambda: fake)
    return fake
