"""Normalize, matmul, argsort — sub-millisecond at corpus scale; no ANN indexes.

The metric is per feature key, not global. Cosine is right for the embedding,
where direction carries the meaning and magnitude mostly tracks loudness. It is
wrong for groove: four hand-normalized, all-positive numbers all point into the
same orthant, so cosine rates every pair 0.99+ and the ordering is noise.
Measured on 150 tracks, AC/DC's nearest groove neighbours under cosine scored
0.999, 0.999, 0.998 and were a country track, a bossa nova and another country
track. Under euclidean the same axis separates properly.

analysis.METRICS is the source of truth for which is which — it lives there
because the right metric follows from how each vector is built.
"""
from __future__ import annotations

import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(norms == 0.0, 1.0, norms)


def scores(seed: np.ndarray, matrix: np.ndarray, metric: str = "cosine") -> np.ndarray:
    """Similarity of seed against every row, higher = more similar.

    "cosine"    -> [-1, 1], angle between vectors.
    "euclidean" -> (0, 1], 1/(1+distance), so it is still a similarity and
                   sorts the same direction as cosine.
    """
    matrix = np.asarray(matrix, dtype=float)
    seed = np.asarray(seed, dtype=float)
    if metric == "euclidean":
        return 1.0 / (1.0 + np.linalg.norm(matrix - seed, axis=-1))
    if metric != "cosine":
        raise ValueError(f"unknown metric {metric!r}")
    return _normalize(matrix) @ _normalize(seed)


def rank(seed: np.ndarray, matrix: np.ndarray, direction: int = 1,
         limit: int = 10, metric: str = "cosine") -> np.ndarray:
    """Row indices, best first. direction=-1 ranks most-distant (surprise)."""
    return np.argsort(direction * scores(seed, matrix, metric))[::-1][:limit]
