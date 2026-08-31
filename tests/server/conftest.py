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

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def smembers(self, key):
        return self.sets.get(key, set())


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(store, "client", lambda: fake)
    return fake
