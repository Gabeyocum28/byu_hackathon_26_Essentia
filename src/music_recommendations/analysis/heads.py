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

import essentia

essentia.log.infoActive = False
essentia.log.warningActive = False

from essentia.standard import TensorflowPredict2D  # noqa: E402

from . import registry  # noqa: E402

_heads: dict | None = None


def _classes(filename: str) -> list[str]:
    meta = registry.MODELS_DIR / filename.replace(".pb", ".json")
    if not meta.exists():
        raise FileNotFoundError(
            f"{meta} missing — run: python scripts/fetch_models.py"
        )
    return json.loads(meta.read_text())["classes"]


def _positive_index(classes: list[str]) -> int:
    """The class that is NOT the negated one, e.g. 'sad' out of [non_sad, sad]."""
    return next(
        i for i, c in enumerate(classes) if not c.lower().startswith(("non_", "not_"))
    )


def _models() -> dict:
    global _heads
    if _heads is None:
        built = {}
        for name, head in registry.HEADS.items():
            path = registry.MODELS_DIR / head.filename
            if not path.exists():
                raise FileNotFoundError(
                    f"{path} missing — run: python scripts/fetch_models.py"
                )
            classes = _classes(head.filename)
            built[name] = (
                TensorflowPredict2D(
                    graphFilename=str(path),
                    input=head.input_node,
                    output=head.output_node,
                ),
                _positive_index(classes) if head.n_out == 2 else None,
            )
        _heads = built
    return _heads


def run_heads(effnet_frames: np.ndarray) -> dict:
    """All heads on one embedding pass. Binary heads reduce to P(positive)."""
    out: dict = {}
    for name, (model, positive) in _models().items():
        activations = model(effnet_frames).mean(axis=0)
        if positive is None:
            out[name] = activations.astype(float)
        else:
            out[name] = float(activations[positive])
    return out
