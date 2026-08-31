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


def run_heads(effnet_frames: "np.ndarray") -> dict:
    """All heads on one embedding pass. Binary heads reduce to P(positive)."""
    raise NotImplementedError
