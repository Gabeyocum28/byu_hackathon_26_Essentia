"""Thin Deezer API client. No auth. Produces contract-shaped Track dicts."""
from __future__ import annotations

API = "https://api.deezer.com"
SLEEP = 0.2  # politeness delay before every API call


def track_to_contract(raw: dict) -> dict | None:
    """Deezer track payload -> contract Track, or None if it has no preview."""
    raise NotImplementedError


def search_tracks(query: str, limit: int = 10) -> list[dict]:
    """Search tracks and return contract-shaped Track dicts."""
    raise NotImplementedError


def search_artist(name: str) -> dict | None:
    """Look up an artist by name; returns {"id", "name"} or None."""
    raise NotImplementedError


def artist_top_tracks(artist_id: int, limit: int = 20) -> list[dict]:
    """An artist's top tracks as contract-shaped Track dicts."""
    raise NotImplementedError


def related_artists(artist_id: int, limit: int = 20) -> list[dict]:
    """Artists related to the given artist id."""
    raise NotImplementedError


def fresh_preview_url(track_id: str) -> str | None:
    """Preview URLs are signed and expire (~15 min); refetch for a new one."""
    raise NotImplementedError
