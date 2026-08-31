"""Redis read/write. Keys:
  track:{id}      -> JSON: contract Track fields
  features:{id}   -> JSON: {feature_key: [floats] | float}
  corpus:ids      -> set of analyzed track ids
"""
from __future__ import annotations


def client() -> "redis.Redis":
    """Lazily construct and cache the Redis client."""
    raise NotImplementedError


def put_track(track: dict, features: dict) -> None:
    """Write a track's contract fields and analyzed features into Redis."""
    raise NotImplementedError


def get_track(track_id: str) -> dict | None:
    """Read a track's contract fields, or None if not present."""
    raise NotImplementedError


def get_features(track_id: str) -> dict | None:
    """Read a track's analyzed features, or None if not present."""
    raise NotImplementedError


def corpus_ids() -> list[str]:
    """All track ids currently analyzed and stored."""
    raise NotImplementedError
