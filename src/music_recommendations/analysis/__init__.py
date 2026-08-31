"""analyze_track: MP3 path in, dict of named feature vectors out (spec §2.1).

Pure — no cache, no HTTP, no Redis. Callers (server, corpus/ingest)
decide when to run it and where results live.
"""
from __future__ import annotations

from pathlib import Path


def analyze_track(mp3_path: Path | str) -> dict:
    from .embedding import effnet_frames
    from .groove import groove_vector
    from .heads import run_heads

    frames = effnet_frames(mp3_path)
    features = {"embedding": frames.mean(axis=0)}
    features.update(run_heads(frames))
    features["groove"] = groove_vector(mp3_path)
    return features
