"""Batch loop: download preview -> analyze_track -> write Redis.

Same analysis function the server calls on demand; different caller
(spec §7). Skips tracks already in Redis; one bad track never kills a run.
"""
from __future__ import annotations


def ingest(tracks: list[dict], limit: int = 300) -> int:
    """Download, analyze, and store up to limit tracks; returns count ingested."""
    raise NotImplementedError
