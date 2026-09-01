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

import heapq
import threading

import numpy as np


_PAIRWISE_LOCK = threading.Lock()
_PAIRWISE_CACHE: tuple[np.ndarray, np.ndarray] | None = None


def clear_geometry_cache() -> None:
    global _PAIRWISE_CACHE
    with _PAIRWISE_LOCK:
        _PAIRWISE_CACHE = None


def normalized_rows(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def pairwise_cosine(matrix: np.ndarray) -> np.ndarray:
    """Dense cosine matrix cached by matrix identity; safe through ~10k rows.

    At 20k rows float64 approaches 3.2 GB, so this intentionally remains a
    small-corpus visualization primitive rather than a ranking dependency.
    """
    global _PAIRWISE_CACHE
    with _PAIRWISE_LOCK:
        if _PAIRWISE_CACHE is not None and _PAIRWISE_CACHE[0] is matrix:
            return _PAIRWISE_CACHE[1]
        unit = normalized_rows(matrix)
        similarity = np.clip(unit @ unit.T, -1.0, 1.0)
        _PAIRWISE_CACHE = (matrix, similarity)
        return similarity


def shortest_walk(matrix: np.ndarray, start: int, end: int,
                  k: int = 8) -> tuple[list[int], float, float]:
    """Dijkstra on the symmetrized k-NN graph of normalized embeddings.

    Neighbor choice is cosine-equivalent. Edge length is the Euclidean chord
    between unit vectors, which preserves that neighbor order and gives the
    metric Isomap needs for a meaningful geodesic/ambient detour ratio.
    """
    matrix = np.asarray(matrix, dtype=float)
    n = len(matrix)
    if not (0 <= start < n and 0 <= end < n):
        raise IndexError("walk endpoint outside matrix")
    if start == end:
        return [start], 0.0, 0.0
    k = min(max(int(k), 1), n - 1)

    similarity = pairwise_cosine(matrix)
    chord = np.sqrt(np.maximum(0.0, 2.0 - 2.0 * similarity))
    adjacency: list[dict[int, float]] = [dict() for _ in range(n)]
    for i in range(n):
        candidates = np.argpartition(chord[i], k)[:k + 1]
        neighbors = [int(j) for j in candidates if j != i]
        neighbors.sort(key=lambda j: (chord[i, j], j))
        for j in neighbors[:k]:
            weight = float(chord[i, j])
            adjacency[i][j] = min(adjacency[i].get(j, weight), weight)
            adjacency[j][i] = min(adjacency[j].get(i, weight), weight)

    distances = [float("inf")] * n
    previous = [-1] * n
    distances[start] = 0.0
    queue = [(0.0, start)]
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == end:
            break
        for neighbor, weight in adjacency[node].items():
            candidate = distance + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))

    if not np.isfinite(distances[end]):
        raise ValueError("k-NN graph is disconnected")
    path = []
    node = end
    while node != -1:
        path.append(node)
        if node == start:
            break
        node = previous[node]
    path.reverse()
    return path, float(distances[end]), float(chord[start, end])


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
