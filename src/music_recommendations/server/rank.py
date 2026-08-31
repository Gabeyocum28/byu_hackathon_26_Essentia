"""Normalize, matmul, argsort — sub-millisecond at corpus scale; no ANN indexes."""
from __future__ import annotations

import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(norms == 0.0, 1.0, norms)


def scores(seed: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of seed against every row."""
    return _normalize(np.asarray(matrix, dtype=float)) @ _normalize(
        np.asarray(seed, dtype=float)
    )


def rank(seed: np.ndarray, matrix: np.ndarray, direction: int = 1,
         limit: int = 10) -> np.ndarray:
    """Row indices, best first. direction=-1 ranks most-distant (surprise)."""
    return np.argsort(direction * scores(seed, matrix))[::-1][:limit]
