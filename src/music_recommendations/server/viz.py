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


_PAIRWISE_LOCK = threading.RLock()
_PAIRWISE_CACHE: tuple[np.ndarray, np.ndarray] | None = None
# (matrix, {k: adjacency}) — the matrix is held in the tuple ON PURPOSE:
# keying by bare id(matrix) let the old array be garbage-collected after a
# corpus growth, and a later array reusing the same address would silently
# serve a graph whose node indices belong to the old, smaller corpus.
_GRAPH_CACHE: tuple[np.ndarray, dict[int, list[dict[int, float]]]] | None = None


def clear_geometry_cache() -> None:
    global _PAIRWISE_CACHE, _GRAPH_CACHE
    with _PAIRWISE_LOCK:
        _PAIRWISE_CACHE = None
        _GRAPH_CACHE = None


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

    Both the k-NN edges and their weights use cosine distance (1 - cosine),
    matching the numbers shown in the walkthrough. The graph is cached by
    matrix identity and k because embedding matrices are already cache-owned
    by the server for the lifetime of a corpus snapshot.
    """
    matrix = np.asarray(matrix, dtype=float)
    n = len(matrix)
    if not (0 <= start < n and 0 <= end < n):
        raise IndexError("walk endpoint outside matrix")
    if start == end:
        return [start], 0.0, 0.0
    k = min(max(int(k), 1), n - 1)

    global _GRAPH_CACHE
    with _PAIRWISE_LOCK:
        if _GRAPH_CACHE is None or _GRAPH_CACHE[0] is not matrix:
            _GRAPH_CACHE = (matrix, {})
        graphs = _GRAPH_CACHE[1]
        adjacency = graphs.get(k)
        if adjacency is None:
            similarity = pairwise_cosine(matrix)
            distance = 1.0 - similarity
            adjacency = [dict() for _ in range(n)]
            for i in range(n):
                candidates = np.argpartition(distance[i], k)[:k + 1]
                neighbors = [int(j) for j in candidates if j != i]
                neighbors.sort(key=lambda j: (distance[i, j], j))
                for j in neighbors[:k]:
                    weight = float(distance[i, j])
                    adjacency[i][j] = min(adjacency[i].get(j, weight), weight)
                    adjacency[j][i] = min(adjacency[j].get(i, weight), weight)
            graphs[k] = adjacency

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
    similarity = pairwise_cosine(matrix)
    return path, float(distances[end]), float(1.0 - similarity[start, end])


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


def project_top8(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(n, d) -> (coords8 (n, 8) float64, variance fractions (8,) float64).

    Same row-normalization, mean-centering, and per-component sign-fixing
    rule as project_2d, extended to all 8 components — columns 0 and 1 are
    numerically identical to project_2d's output (same SVD, same sign
    convention), so one SVD serves /viz/map, /viz/walk, and /viz/tour.

    variance[i] is s_i^2 over the FULL spectrum of the thin SVD (all
    min(n, d) singular values), not just the top 8, per T2.1's talking
    point ("Top-8 PCs hold 37.4% of variance").

    d < 8 corpora (including the fixture-sized ones in tests) pad the
    unused columns with zeros rather than erroring.
    """
    matrix = np.asarray(matrix, dtype=float)
    n = matrix.shape[0]
    if n < 2:
        return np.zeros((n, 8)), np.zeros(8)

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    unit = matrix / np.where(norms == 0.0, 1.0, norms)
    centered = unit - unit.mean(axis=0)

    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    total_variance = float(np.sum(s ** 2))
    k = min(8, u.shape[1])
    coords = u[:, :k] * s[:k]

    # Fix the sign convention per component: make each component's
    # largest-magnitude coordinate positive (same rule as project_2d).
    for col in range(k):
        peak = np.argmax(np.abs(coords[:, col]))
        if coords[peak, col] < 0:
            coords[:, col] = -coords[:, col]

    if k < 8:
        coords = np.hstack([coords, np.zeros((n, 8 - k))])

    variance = np.zeros(8)
    if total_variance > 0.0:
        variance[:k] = (s[:k] ** 2) / total_variance
    return coords, variance


def minimum_spanning_tree(matrix: np.ndarray) -> list[tuple[int, int, float]]:
    """Prim's algorithm over the dense cosine-distance matrix.

    Returns exactly n-1 (i, j, d) edges, i < j, sorted ascending by d.
    Deterministic tie-breaking: when multiple unvisited nodes tie for the
    cheapest edge, the lowest index wins. Reuses pairwise_cosine's cache,
    so this stays cheap through the ~10k-row scale that primitive already
    documents; not engineered past it.
    """
    matrix = np.asarray(matrix, dtype=float)
    n = len(matrix)
    if n < 2:
        return []

    distance = 1.0 - pairwise_cosine(matrix)

    in_tree = np.zeros(n, dtype=bool)
    best_dist = distance[0].copy()
    best_from = np.zeros(n, dtype=int)
    in_tree[0] = True
    best_dist[0] = np.inf

    edges: list[tuple[int, int, float]] = []
    for _ in range(n - 1):
        masked = np.where(in_tree, np.inf, best_dist)
        min_val = float(masked.min())
        j = int(np.flatnonzero(masked == min_val)[0])
        i = int(best_from[j])
        a, b = (i, j) if i < j else (j, i)
        edges.append((a, b, min_val))

        in_tree[j] = True
        candidate = distance[j]
        better = (~in_tree) & (candidate < best_dist)
        best_dist = np.where(better, candidate, best_dist)
        best_from = np.where(better, j, best_from)

    edges.sort(key=lambda e: (e[2], e[0], e[1]))
    return edges


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
