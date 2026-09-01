"""Math for GET /viz/map — the demo/debug galaxy of embedding space.

NOT part of contract/contract.md (like GET /). The map is always a 2D PCA of
the EMBEDDING matrix regardless of axis: the picture answers "where does the
music lie", the axis only changes which scores are attached to the recs.

PCA over eigen-libraries: the corpus is numpy-sized, the projection is two
principal components of an (n, 1280) matrix, and we already hold that matrix
in process (app._MATRIX_CACHE). Rows are L2-normalized first so the picture
matches the cosine geometry the ranking actually uses — otherwise loudness
becomes the first principal component.
"""
from __future__ import annotations

import numpy as np


def project_2d(matrix: np.ndarray) -> np.ndarray:
    """(n, d) -> (n, 2): first two principal components of the row-normalized,
    mean-centered matrix. Deterministic (sign-fixed) so points don't jump
    between requests as the corpus grows."""
    matrix = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    unit = matrix / np.where(norms == 0.0, 1.0, norms)
    centered = unit - unit.mean(axis=0)

    if centered.shape[0] < 2:
        return np.zeros((centered.shape[0], 2))

    # SVD of the thin side: components are V rows, coordinates U * S.
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    xy = u[:, :2] * s[:2]
    if xy.shape[1] < 2:  # degenerate d == 1
        xy = np.hstack([xy, np.zeros((xy.shape[0], 1))])

    # Fix the sign convention: make each component's largest-magnitude
    # coordinate positive, so the layout is stable across recomputes.
    for col in range(2):
        peak = np.argmax(np.abs(xy[:, col]))
        if xy[peak, col] < 0:
            xy[:, col] = -xy[:, col]
    return xy


def score_math(seed_vec: np.ndarray, rec_vec: np.ndarray, metric: str,
               centrality: float | None) -> dict:
    """The numbers behind one recommendation's score, for the math panel.

    cosine:    score == dot / (seed_norm * rec_norm)
    euclidean: score == 1 / (1 + distance)
    """
    seed_vec = np.asarray(seed_vec, dtype=float)
    rec_vec = np.asarray(rec_vec, dtype=float)
    return {
        "metric": metric,
        "dot": float(seed_vec @ rec_vec),
        "seed_norm": float(np.linalg.norm(seed_vec)),
        "rec_norm": float(np.linalg.norm(rec_vec)),
        "distance": (
            float(np.linalg.norm(seed_vec - rec_vec))
            if metric == "euclidean" else None
        ),
        "centrality": centrality,
    }
