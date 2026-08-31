"""Run every registry head over one set of EffNet frames (~0.01 s each).

Binary mood heads do NOT agree on which class index is "positive" — verified
against models/*.json: mood_happy is [happy, non_happy] (positive=0) but
mood_sad is [non_sad, sad] (positive=1), mood_relaxed is
[non_relaxed, relaxed] (positive=1), and mood_aggressive is
[aggressive, not_aggressive] (positive=0). The index is resolved per-head
from the model's own JSON metadata (classes list) rather than assumed,
matching the legacy analyzer's approach.
"""
from __future__ import annotations

import json

import numpy as np

from .registry import HEADS, MODELS_DIR

_loaded: dict = {}
_positive_index: dict = {}


def _positive_class_index(name: str) -> int:
    if name not in _positive_index:
        h = HEADS[name]
        meta_path = MODELS_DIR / (h.filename[: -len(".pb")] + ".json")
        classes = json.loads(meta_path.read_text())["classes"]
        _positive_index[name] = next(
            i for i, c in enumerate(classes) if not c.startswith(("non_", "not_"))
        )
    return _positive_index[name]


def _head(name: str):
    from essentia.standard import TensorflowPredict2D

    if name not in _loaded:
        h = HEADS[name]
        _loaded[name] = TensorflowPredict2D(
            graphFilename=str(MODELS_DIR / h.filename),
            input=h.input_node,
            output=h.output_node,
        )
    return _loaded[name]


def run_heads(effnet_frames: np.ndarray) -> dict:
    """All heads on one embedding pass. Binary heads reduce to P(positive)."""
    out: dict = {}
    for name, spec in HEADS.items():
        act = _head(name)(effnet_frames).mean(axis=0)
        if spec.n_out == 2:
            out[name] = float(act[_positive_class_index(name)])
        else:
            out[name] = act
    return out
