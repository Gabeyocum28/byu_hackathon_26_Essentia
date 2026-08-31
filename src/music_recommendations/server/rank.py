"""Normalize, matmul, argsort — sub-millisecond at corpus scale; no ANN indexes."""
from __future__ import annotations


def scores(seed: "np.ndarray", matrix: "np.ndarray") -> "np.ndarray":
    """Cosine similarity of seed against every row."""
    raise NotImplementedError


def rank(seed: "np.ndarray", matrix: "np.ndarray", direction: int = 1,
         limit: int = 10) -> "np.ndarray":
    """Row indices, best first. direction=-1 ranks most-distant (surprise)."""
    raise NotImplementedError
