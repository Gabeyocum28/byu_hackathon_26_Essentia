"""rank.py: normalize + matmul + argsort, per spec §2.2."""
import numpy as np
import pytest

from music_recommendations.server import rank


def test_scores_is_cosine_similarity():
    seed = np.array([1.0, 0.0])
    matrix = np.array([
        [1.0, 0.0],    # identical -> 1.0
        [0.0, 1.0],    # orthogonal -> 0.0
        [-1.0, 0.0],   # opposite -> -1.0
        [2.0, 0.0],    # same direction, bigger magnitude -> still 1.0
    ])
    s = rank.scores(seed, matrix)
    assert s == pytest.approx([1.0, 0.0, -1.0, 1.0])


def test_scores_zero_vector_yields_zero_not_nan():
    seed = np.array([1.0, 0.0])
    matrix = np.array([[0.0, 0.0], [1.0, 0.0]])
    s = rank.scores(seed, matrix)
    assert not np.isnan(s).any()
    assert s[0] == 0.0


def test_rank_returns_nearest_first():
    seed = np.array([1.0, 0.0])
    matrix = np.array([
        [0.0, 1.0],     # orthogonal
        [1.0, 0.1],     # very close
        [-1.0, 0.0],    # opposite
        [1.0, 1.0],     # 45 degrees
    ])
    idx = rank.rank(seed, matrix, limit=4)
    assert list(idx) == [1, 3, 0, 2]


def test_rank_direction_negative_returns_most_distant_first():
    seed = np.array([1.0, 0.0])
    matrix = np.array([[1.0, 0.1], [0.0, 1.0], [-1.0, 0.0]])
    idx = rank.rank(seed, matrix, direction=-1, limit=3)
    assert list(idx) == [2, 1, 0]


def test_rank_respects_limit():
    seed = np.array([1.0, 0.0])
    matrix = np.random.default_rng(0).normal(size=(20, 2))
    idx = rank.rank(seed, matrix, limit=5)
    assert len(idx) == 5
