"""Thin Deezer API client: search, charts, related artists, preview download."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.deezer.com"


def _get(path: str, **params) -> dict:
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def _slim(track: dict) -> dict:
    """Keep the metadata fields the MVP cares about."""
    return {
        "id": track["id"],
        "title": track["title"],
        "artist": track["artist"]["name"],
        "artist_id": track["artist"]["id"],
        "album": track.get("album", {}).get("title", ""),
        "duration": track.get("duration", 0),
        "rank": track.get("rank", 0),  # Deezer popularity
        "preview": track.get("preview") or "",
        "link": track.get("link", ""),
    }


def search_tracks(query: str, limit: int = 5) -> list[dict]:
    data = _get("/search", q=query, limit=limit).get("data", [])
    return [_slim(t) for t in data if t.get("preview")]


def chart_tracks(limit: int = 20) -> list[dict]:
    data = _get("/chart/0/tracks", limit=limit).get("data", [])
    return [_slim(t) for t in data if t.get("preview")]


def artist_top_tracks(artist_id: int, limit: int = 5) -> list[dict]:
    data = _get(f"/artist/{artist_id}/top", limit=limit).get("data", [])
    return [_slim(t) for t in data if t.get("preview")]


def related_artists(artist_id: int, limit: int = 10) -> list[dict]:
    data = _get(f"/artist/{artist_id}/related", limit=limit).get("data", [])
    return [{"id": a["id"], "name": a["name"]} for a in data]


def download_preview(track: dict, dest_dir: Path) -> Path:
    """Download a track's 30s preview MP3 (cached by track id).

    Preview URLs are signed and expire after ~15 minutes; on a 403 we
    re-fetch the track from the API for a fresh URL and retry once.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9 _-]", "_", f"{track['artist']} - {track['title']}")
    path = dest_dir / f"{track['id']}_{safe[:60]}.mp3"
    if not path.exists():
        try:
            urllib.request.urlretrieve(track["preview"], path)
        except urllib.error.HTTPError as exc:
            if exc.code != 403:
                raise
            fresh = _get(f"/track/{track['id']}").get("preview")
            if not fresh:
                raise
            track["preview"] = fresh
            urllib.request.urlretrieve(fresh, path)
    return path
