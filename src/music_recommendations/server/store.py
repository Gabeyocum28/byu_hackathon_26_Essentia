"""Redis read/write. Keys:
  track:{id}      -> JSON: contract Track fields
  features:{id}   -> JSON: {feature_key: [floats] | float}
  corpus:ids      -> set of analyzed track ids

With CORPUS_SNAPSHOT set, the corpus is read from files instead and every
function here forwards to snapshot.py -- see that module for why. Redis stays
the path on the Mac, where the crawler and embed worker need somewhere to
write; the switch exists so the hosted server can run without a Redis at all.
"""
from __future__ import annotations

import json
import os

from music_recommendations.server import snapshot

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
    if snapshot.active():
        snapshot.put_track(track, features)
        return
    r = client()
    track_id = track["track_id"]
    r.set(f"track:{track_id}", json.dumps(track))
    r.set(f"features:{track_id}", json.dumps(features))
    r.sadd("corpus:ids", track_id)


def get_track(track_id: str) -> dict | None:
    """Read a track's contract fields, or None if not present."""
    if snapshot.active():
        return snapshot.get_track(track_id)
    raw = client().get(f"track:{track_id}")
    return json.loads(raw) if raw else None


def get_many_tracks(track_ids: list[str]) -> list[dict | None]:
    """Read many track records in one round trip, preserving input order."""
    if snapshot.active():
        return snapshot.get_many_tracks(track_ids)
    if not track_ids:
        return []
    raw = client().mget([f"track:{t}" for t in track_ids])
    return [json.loads(record) if record else None for record in raw]


def get_features(track_id: str) -> dict | None:
    """Read a track's analyzed features, or None if not present."""
    if snapshot.active():
        return snapshot.get_features(track_id)
    raw = client().get(f"features:{track_id}")
    return json.loads(raw) if raw else None


def corpus_size() -> int:
    """How many tracks are analyzed, without transferring their ids.

    corpus_ids() ships every id and sorts them; at corpus scale that is real
    time on a path that runs per request. Tracks are only ever added, so the
    count alone is a sound signal for "has anything changed".
    """
    if snapshot.active():
        return snapshot.corpus_size()
    return client().scard("corpus:ids")


# corpus_ids ships every id out of Redis and sorts them. On a 90k corpus that
# is ~1 MB of strings and a full sort, paid on every /recommend. Tracks are only
# ever ADDED, so the cardinality is a sound "has anything changed" signal, and
# SCARD is O(1) -- check that first and reuse the last list when it matches.
_ids_cache: tuple[int, list[str]] | None = None


def corpus_ids() -> list[str]:
    """All track ids currently analyzed and stored, sorted."""
    if snapshot.active():
        return snapshot.corpus_ids()
    global _ids_cache
    size = client().scard("corpus:ids")
    if _ids_cache is not None and _ids_cache[0] == size:
        return _ids_cache[1]
    ids = sorted(client().smembers("corpus:ids"))
    _ids_cache = (size, ids)
    return ids


def get_many_features(track_ids: list[str]) -> list[dict | None]:
    """Read many tracks' features in one round trip, in the order asked for.

    /recommend needs every vector in the corpus. One GET per track is one
    network round trip per track, which is what the endpoint's cost actually
    was at corpus scale -- 25 s at 7.8k tracks, and linear from there.
    """
    if snapshot.active():
        return snapshot.get_many_features(track_ids)
    if not track_ids:
        return []
    raw = client().mget([f"features:{t}" for t in track_ids])
    return [json.loads(r) if r else None for r in raw]


# ---- embed work queue (internal; not part of the HTTP contract) ----
#   embed:queue        -> list of track ids awaiting analysis (LPUSH/BRPOP)
#   embed:queued       -> set guarding against duplicate enqueues
#   embed:queued:{id}  -> TTL companion: a set member can't expire on its
#                         own, so a crashed worker blocks re-enqueue for at
#                         most this long.

_QUEUED_TTL_S = 300


def put_track_meta(track: dict) -> None:
    """Write a track's contract fields only — no features, no corpus entry."""
    if snapshot.active():
        snapshot.put_track_meta(track)
        return
    client().set(f"track:{track['track_id']}", json.dumps(track))


def enqueue_embed(track_id: str) -> bool:
    """Queue a track for the embed worker. False if already queued.

    The guard-then-push below isn't atomic: two concurrent callers can both
    pass the check and both LPUSH. Harmless -- the worker's writes are
    idempotent, so a track processed twice just costs an extra analysis.
    """
    r = client()
    if r.sismember("embed:queued", track_id) and r.exists(f"embed:queued:{track_id}"):
        return False
    r.sadd("embed:queued", track_id)
    r.set(f"embed:queued:{track_id}", "1", ex=_QUEUED_TTL_S)
    r.lpush("embed:queue", track_id)
    return True


def dequeue_embed(timeout: int = 5) -> str | None:
    """Block up to `timeout` seconds for the next queued track id."""
    popped = client().brpop("embed:queue", timeout=timeout)
    return popped[1] if popped else None


def clear_embed_marker(track_id: str) -> None:
    """Drop the dedup guard so the track can be enqueued again."""
    r = client()
    r.srem("embed:queued", track_id)
    r.delete(f"embed:queued:{track_id}")


# ---- attribution work queue + cache (T2.6; internal, like embed above) ----
#   attr:queue           -> list of "seed|rec" jobs awaiting the worker
#   attr:queued:{pair}   -> TTL guard against re-enqueueing a pending pair
#   viz:attr:{seed}:{rec}-> the finished (or failed) result, JSON

_ATTR_QUEUED_TTL_S = 300


def _attr_pair(seed_id: str, rec_id: str) -> str:
    return f"{seed_id}|{rec_id}"


def get_attribution(seed_id: str, rec_id: str) -> dict | None:
    raw = client().get(f"viz:attr:{seed_id}:{rec_id}")
    return json.loads(raw) if raw else None


def put_attribution(seed_id: str, rec_id: str, payload: dict,
                    ttl: int | None = None) -> None:
    """Cache one pair's attribution. A ready result is kept forever (the
    corpus embedding it describes doesn't change); a failure gets a TTL so
    the pair is retried instead of being wrong until someone clears Redis."""
    client().set(f"viz:attr:{seed_id}:{rec_id}", json.dumps(payload), ex=ttl)


def enqueue_attribution(seed_id: str, rec_id: str) -> bool:
    """Queue a pair for the worker. False if this pair is already pending."""
    r = client()
    pair = _attr_pair(seed_id, rec_id)
    if r.exists(f"attr:queued:{pair}"):
        return False
    r.set(f"attr:queued:{pair}", "1", ex=_ATTR_QUEUED_TTL_S)
    r.lpush("attr:queue", pair)
    return True


def dequeue_job(timeout: int = 5) -> tuple[str, str] | None:
    """Next job from either queue as (kind, payload).

    One blocking pop over both lists: BRPOP takes the first non-empty key in
    order, so an embed job (a human waiting on a seed) always wins over an
    attribution job (a background explanation).
    """
    popped = client().brpop(["embed:queue", "attr:queue"], timeout=timeout)
    if not popped:
        return None
    key, value = popped
    return ("embed" if key.endswith("embed:queue") else "attribution"), value


def clear_attribution_marker(seed_id: str, rec_id: str) -> None:
    client().delete(f"attr:queued:{_attr_pair(seed_id, rec_id)}")


# ---- signed preview URL cache (internal; see GET /preview) ----
#   preview:{id} -> the last freshly signed Deezer preview URL
#
# Deezer's signature lives ~15 minutes. Caching for 10 leaves a margin wide
# enough that a URL handed out at the end of the window still plays, while
# collapsing repeat plays of the same track onto one API call instead of one
# per tap -- Deezer throttles, and /preview is on the play path.

_PREVIEW_TTL_S = 600


def get_cached_preview(track_id: str) -> str | None:
    """The cached signed URL for a track, or None if absent or aged out."""
    if snapshot.active():
        return snapshot.get_cached_preview(track_id)
    return client().get(f"preview:{track_id}")


def put_cached_preview(track_id: str, url: str, ttl: int = _PREVIEW_TTL_S) -> None:
    """Cache one freshly signed URL, expiring well inside its signature."""
    if snapshot.active():
        snapshot.put_cached_preview(track_id, url, ttl)
        return
    client().set(f"preview:{track_id}", url, ex=ttl)
