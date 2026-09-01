"""Deezer search proxy for GET /search; contract Track shape out.

Stdlib urllib on purpose: the runtime deps have no HTTP client and adding
one needs team agreement (AGENTS.md). Swap for httpx if it ever lands.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://api.deezer.com"
TIMEOUT = 5.0


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _to_track(item: dict) -> dict:
    return {
        "track_id": str(item["id"]),
        "title": item["title"],
        "artist": item["artist"]["name"],
        "album": item["album"]["title"],
        "artwork_url": item["album"]["cover_medium"],
        "preview_url": item["preview"],
    }


def search(query: str, limit: int = 25) -> list[dict]:
    """Search Deezer and return contract-shaped Track dicts (preview required),
    most popular first.

    Deezer's fuzzy search misses exact titles with punctuation ("Sing About
    Me, I'm Dying Of Thirst" returns only lofi covers), while its
    track:"..." field search finds the original — so both are queried and
    the union is ordered by Deezer's popularity score ('rank'), which puts
    the well-known recording above covers. The plain query's failure
    propagates (the /search fixture fallback depends on it); the extra
    exact query is best-effort.
    """
    data = _search_data(query, limit)
    try:
        exact = _search_data(f'track:"{query}"', limit)
    except Exception:
        exact = []
    seen: set = set()
    merged = []
    for item in data + exact:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        merged.append(item)
    merged.sort(key=lambda i: i.get("rank", 0), reverse=True)
    return [_to_track(i) for i in merged if i.get("preview")][:limit]


def _search_data(q: str, limit: int) -> list[dict]:
    query = urllib.parse.urlencode({"q": q, "limit": limit})
    return _get_json(f"{API}/search?{query}").get("data", [])


def get_track(track_id: str) -> dict | None:
    """Fetch one track by id, contract-shaped, or None if absent/no preview."""
    item = _get_json(f"{API}/track/{track_id}")
    if not item.get("id") or not item.get("preview"):
        return None
    return _to_track(item)
