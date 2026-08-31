"""Thin Deezer API client. No auth. Produces contract-shaped Track dicts."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.deezer.com"
SLEEP = 0.2  # politeness delay before every API call


def _get(path: str, **params) -> dict:
    time.sleep(SLEEP)
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def track_to_contract(raw: dict) -> dict | None:
    """Deezer track payload -> contract Track, or None if it has no preview."""
    if not raw.get("preview"):
        return None
    return {
        "track_id": str(raw["id"]),
        "title": raw["title"],
        "artist": raw["artist"]["name"],
        "album": raw.get("album", {}).get("title", ""),
        "artwork_url": raw.get("album", {}).get("cover_medium", ""),
        "preview_url": raw["preview"],
    }


def search_tracks(query: str, limit: int = 10) -> list[dict]:
    data = _get("/search", q=query, limit=limit).get("data", [])
    return [t for t in map(track_to_contract, data) if t]


def search_artist(name: str) -> dict | None:
    data = _get("/search/artist", q=name, limit=1).get("data", [])
    return {"id": data[0]["id"], "name": data[0]["name"]} if data else None


def artist_top_tracks(artist_id: int, limit: int = 20) -> list[dict]:
    data = _get(f"/artist/{artist_id}/top", limit=limit).get("data", [])
    return [t for t in map(track_to_contract, data) if t]


def related_artists(artist_id: int, limit: int = 20) -> list[dict]:
    data = _get(f"/artist/{artist_id}/related", limit=limit).get("data", [])
    return [{"id": a["id"], "name": a["name"]} for a in data]


def fresh_preview_url(track_id: str) -> str | None:
    """Preview URLs are signed and expire (~15 min); refetch for a new one."""
    return _get(f"/track/{track_id}").get("preview") or None
