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


def centrality(matrix: np.ndarray, metric: str = "cosine") -> np.ndarray:
    """Each row's mean similarity to the whole corpus.

    Used to stop `surprise` collapsing onto the same handful of tracks. In a
    1280-d space some tracks sit far from *everything*, so a plain argmin
    returns them for every seed regardless of what was seeded — measured on a
    150-track pool, one track was the top answer for 22% of seeds.

    Computed via the identity mean_j(x_i . x_j) == x_i . mean_j(x_j), which is
    O(n*d) rather than the O(n^2) full similarity matrix. That matters: at
    10,000 tracks the naive matrix is 0.4 GB, this is 40 KB.
    """
    matrix = np.asarray(matrix, dtype=float)
    if metric == "cosine":
        unit = _normalize(matrix)
        return unit @ unit.mean(axis=0)
    if metric != "euclidean":
        raise ValueError(f"unknown metric {metric!r}")
    # No shortcut for euclidean; corpora are small enough for the direct form.
    return np.array([scores(row, matrix, metric).mean() for row in matrix])


def rank(seed: np.ndarray, matrix: np.ndarray, direction: int = 1,
         limit: int = 10, metric: str = "cosine",
         correction: np.ndarray | None = None) -> np.ndarray:
    """Row indices, best first. direction=-1 ranks most-distant (surprise).

    `correction` is subtracted from the scores before sorting — pass
    centrality(matrix) on the surprise axis so the result answers "far from
    THIS seed" instead of "far from everything".
    """
    ranked = scores(seed, matrix, metric)
    if correction is not None:
        ranked = ranked - correction
    return np.argsort(direction * ranked)[::-1][:limit]
