"""Snowball crawl: 8 roots -> 2 hops of /related -> top tracks, deduped."""
from __future__ import annotations

ROOTS = [
    "Miles Davis", "Duke Ellington", "Django Reinhardt", "Ornette Coleman",
    "Bill Evans", "Stan Getz", "Jimmy Smith", "Weather Report",
]


def snowball_artists(root_names: list[str], hops: int = 2, per_artist: int = 20) -> list[dict]:
    """BFS out from root_names over /related, deduped by artist id."""
    raise NotImplementedError


def snowball(root_names: list[str] = ROOTS, hops: int = 2, per_artist: int = 20) -> list[dict]:
    """All candidate tracks (contract shape, preview required), deduped by id."""
    raise NotImplementedError
