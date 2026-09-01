"""analyze_track: MP3 path in, dict of named feature vectors out (spec §2.1).

Pure — no cache, no HTTP, no Redis. Callers (server, corpus/ingest)
decide when to run it and where results live. Returned dict keys must
match contract/features.py FEATURE_KEYS.

Callers that persist or compare these vectors also want FEATURES_VERSION
and METRICS from .schema — the version to know when cached vectors went
stale, the metrics to know how to compare them. Import them from
music_recommendations.analysis.schema directly to skip loading essentia.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .schema import FEATURES_VERSION, METRICS

__all__ = ["analyze_track", "as_json", "FEATURES_VERSION", "METRICS"]


def analyze_track(mp3_path: Path | str) -> dict:
    """Run embedding + classification heads; returns the full feature dict."""
    # Imported here, not at module scope: importing essentia pulls TensorFlow
    # and costs ~1 s, and a caller that only wants FEATURES_VERSION or METRICS
    # to check whether its cache is stale should not pay that.
    from . import embedding, heads

    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(mp3_path)

    # The one slow pass. Every classification head rides on its output, so
    # EffNet must never be instantiated twice per track (spec §2.1).
    frames = embedding.effnet_frames(mp3_path)

    # Heads run on the frame-MEAN, not the frames. Mathematically that is
    # prediction-of-mean rather than mean-of-prediction, which is a real
    # difference -- but it is the only form available when backfilling a head
    # onto a corpus that stored just the mean, and a corpus holding both
    # vintages would rank them against each other silently. Same input, same
    # answer, whether a track was analyzed today or backfilled from Redis.
    mean = frames.mean(axis=0).astype(float)
    features = {"embedding": mean}
    features.update(heads.run_heads(mean[None, :]))
    return features


def as_json(features: dict) -> dict:
    """Feature dict with ndarrays flattened to lists, for storage or transport."""
    return {
        k: v.tolist() if isinstance(v, np.ndarray) else float(v)
        for k, v in features.items()
    }
