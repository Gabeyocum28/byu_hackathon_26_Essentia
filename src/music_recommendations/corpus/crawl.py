"""Snowball crawl: 8 roots -> 2 hops of /related -> top tracks, deduped."""
from __future__ import annotations

from . import deezer

ROOTS = [
    "Miles Davis", "Duke Ellington", "Django Reinhardt", "Ornette Coleman",
    "Bill Evans", "Stan Getz", "Jimmy Smith", "Weather Report",
]


def snowball_artists(root_names: list[str], hops: int = 2, per_artist: int = 20) -> list[dict]:
    seen: dict[int, dict] = {}
    frontier = [a for a in (deezer.search_artist(n) for n in root_names) if a]
    for artist in frontier:
        seen[artist["id"]] = artist
    for _ in range(hops):
        nxt = []
        for artist in frontier:
            for rel in deezer.related_artists(artist["id"], limit=per_artist):
                if rel["id"] not in seen:
                    seen[rel["id"]] = rel
                    nxt.append(rel)
        frontier = nxt
    return list(seen.values())


def snowball(root_names: list[str] = ROOTS, hops: int = 2, per_artist: int = 20) -> list[dict]:
    """All candidate tracks (contract shape, preview required), deduped by id."""
    tracks: dict[str, dict] = {}
    for artist in snowball_artists(root_names, hops, per_artist):
        for t in deezer.artist_top_tracks(artist["id"], limit=per_artist):
            tracks.setdefault(t["track_id"], t)
    return list(tracks.values())
