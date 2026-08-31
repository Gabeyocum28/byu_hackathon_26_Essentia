"""analyze_track: MP3 path in, dict of named feature vectors out (spec §2.1).

Pure — no cache, no HTTP, no Redis. Callers (server, corpus/ingest)
decide when to run it and where results live. Returned dict keys must
match contract/features.py FEATURE_KEYS.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import embedding, groove, heads


def analyze_track(mp3_path: Path | str) -> dict:
    """Run embedding + heads + groove extraction; returns the full feature dict."""
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(mp3_path)

    # The one slow pass. Every classification head rides on its output, so
    # EffNet must never be instantiated twice per track (spec §2.1).
    frames = embedding.effnet_frames(mp3_path)

    features = {"embedding": frames.mean(axis=0).astype(float)}
    features.update(heads.run_heads(frames))
    features["groove"] = groove.groove_vector(mp3_path)
    return features


def as_json(features: dict) -> dict:
    """Feature dict with ndarrays flattened to lists, for storage or transport."""
    return {
        k: v.tolist() if isinstance(v, np.ndarray) else float(v)
        for k, v in features.items()
    }
