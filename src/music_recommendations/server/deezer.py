"""Deezer search proxy for GET /search; contract Track shape out."""
from __future__ import annotations

API = "https://api.deezer.com"


def search(query: str, limit: int = 10) -> list[dict]:
    """Search Deezer and return contract-shaped Track dicts (preview required)."""
    raise NotImplementedError
