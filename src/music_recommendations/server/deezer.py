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


def search(query: str, limit: int = 10) -> list[dict]:
    """Search Deezer and return contract-shaped Track dicts (preview required)."""
    q = urllib.parse.urlencode({"q": query, "limit": limit})
    data = _get_json(f"{API}/search?{q}").get("data", [])
    return [_to_track(item) for item in data if item.get("preview")]


def get_track(track_id: str) -> dict | None:
    """Fetch one track by id, contract-shaped, or None if absent/no preview."""
    item = _get_json(f"{API}/track/{track_id}")
    if not item.get("id") or not item.get("preview"):
        return None
    return _to_track(item)
