"""Redis read/write. Keys:
  track:{id}      -> JSON: contract Track fields
  features:{id}   -> JSON: {feature_key: [floats] | float}
  corpus:ids      -> set of analyzed track ids
"""
from __future__ import annotations

import json
import os

_client = None


def client() -> "redis.Redis":
    """Lazily construct and cache the Redis client."""
    global _client
    if _client is None:
        import redis

        _client = redis.Redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
    return _client


def put_track(track: dict, features: dict) -> None:
    """Write a track's contract fields and analyzed features into Redis."""
    r = client()
    track_id = track["track_id"]
    r.set(f"track:{track_id}", json.dumps(track))
    r.set(f"features:{track_id}", json.dumps(features))
    r.sadd("corpus:ids", track_id)


def get_track(track_id: str) -> dict | None:
    """Read a track's contract fields, or None if not present."""
    raw = client().get(f"track:{track_id}")
    return json.loads(raw) if raw else None


def get_features(track_id: str) -> dict | None:
    """Read a track's analyzed features, or None if not present."""
    raw = client().get(f"features:{track_id}")
    return json.loads(raw) if raw else None


def corpus_ids() -> list[str]:
    """All track ids currently analyzed and stored."""
    return sorted(client().smembers("corpus:ids"))


def get_many_features(track_ids: list[str]) -> list[dict | None]:
    """Read many tracks' features in one round trip, in the order asked for.

    /recommend needs every vector in the corpus. One GET per track is one
    network round trip per track, which is what the endpoint's cost actually
    was at corpus scale -- 25 s at 7.8k tracks, and linear from there.
    """
    if not track_ids:
        return []
    raw = client().mget([f"features:{t}" for t in track_ids])
    return [json.loads(r) if r else None for r in raw]
