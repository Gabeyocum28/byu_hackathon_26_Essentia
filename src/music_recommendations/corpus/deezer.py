"""Thin Deezer API client. No auth. Produces contract-shaped Track dicts."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.deezer.com"
SLEEP = 0.2  # politeness delay before every API call
TIMEOUT = 20
RETRIES = 3

_last_call = 0.0
# The downloader refetches expired preview URLs from many threads at once, so
# the delay has to be held under a lock or it is not a delay at all.
_call_lock = threading.Lock()


def _get(path: str, **params) -> dict:
    """One GET, rate-limited and retried. Returns {} rather than raising.

    Deezer signals throttling with HTTP 200 and an "error" object in the body,
    not a 429, so the body has to be inspected. A crawl of a few thousand
    tracks will hit this; backing off and continuing beats losing the run.
    """
    global _last_call
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    for attempt in range(RETRIES):
        with _call_lock:
            elapsed = time.monotonic() - _last_call
            if elapsed < SLEEP:
                time.sleep(SLEEP - elapsed)
            _last_call = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(SLEEP * 4 * (attempt + 1))
            continue
        if isinstance(payload, dict) and "error" in payload:
            # Quota exceeded is the common one; anything else is not retryable.
            if "Quota" not in str(payload["error"]):
                return {}
            time.sleep(SLEEP * 10 * (attempt + 1))
            continue
        return payload
    return {}


def track_to_contract(raw: dict) -> dict | None:
    """Deezer track payload -> contract Track, or None if it has no preview."""
    if not raw.get("preview") or not raw.get("id"):
        return None
    album = raw.get("album") or {}
    artist = raw.get("artist") or {}
    return {
        "track_id": str(raw["id"]),
        "title": raw.get("title", ""),
        "artist": artist.get("name", ""),
        "album": album.get("title", ""),
        "artwork_url": album.get("cover_medium") or album.get("cover") or "",
        "preview_url": raw["preview"],
    }


def _tracks(payload: dict, limit: int) -> list[dict]:
    out = []
    for raw in payload.get("data", []):
        track = track_to_contract(raw)
        if track:
            out.append(track)
        if len(out) >= limit:
            break
    return out


def search_tracks(query: str, limit: int = 10) -> list[dict]:
    """Search tracks and return contract-shaped Track dicts."""
    return _tracks(_get("/search", q=query, limit=limit), limit)


def search_artist(name: str) -> dict | None:
    """Look up an artist by name; returns {"id", "name"} or None."""
    for raw in _get("/search/artist", q=name, limit=1).get("data", []):
        return {"id": raw["id"], "name": raw["name"]}
    return None


def artist_top_tracks(artist_id: int, limit: int = 20) -> list[dict]:
    """An artist's top tracks as contract-shaped Track dicts."""
    return _tracks(_get(f"/artist/{artist_id}/top", limit=limit), limit)


def related_artists(artist_id: int, limit: int = 20) -> list[dict]:
    """Artists related to the given artist id."""
    return [
        {"id": raw["id"], "name": raw["name"]}
        for raw in _get(f"/artist/{artist_id}/related", limit=limit).get("data", [])
    ][:limit]


def chart_tracks(genre_id: int, limit: int = 100) -> list[dict]:
    """Top tracks for a Deezer genre.

    /genre/{id}/artists is NOT genre-filtered (spec §2.3 checked: genre 129
    returns Dolly Parton and Drake). /chart/{id}/tracks is, and it is the only
    cheap way to seed a corpus that spans genres rather than one artist graph.
    Capped at 100 by Deezer.
    """
    return _tracks(_get(f"/chart/{genre_id}/tracks", limit=limit), limit)


def fresh_preview_url(track_id: str) -> str | None:
    """Preview URLs are signed and expire (~15 min); refetch for a new one."""
    return _get(f"/track/{track_id}").get("preview") or None
