"""analyze_track: MP3 path in, dict of named feature vectors out (spec §2.1).

Pure — no cache, no HTTP, no Redis. Callers (server, corpus/ingest)
decide when to run it and where results live. Returned dict keys must
match contract/features.py FEATURE_KEYS.
"""
from __future__ import annotations

from pathlib import Path


def analyze_track(mp3_path: Path | str) -> dict:
    """Run embedding + heads + groove extraction; returns the full feature dict."""
    raise NotImplementedError
