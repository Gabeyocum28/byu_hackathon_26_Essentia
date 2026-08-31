"""Tests for the pure similarity math in mvp/similarity.py."""

import numpy as np
import pytest

from mvp.similarity import (
    bpm_score,
    camelot,
    connection,
    embedding_score,
    key_score,
)


class TestCamelot:
    def test_known_positions(self):
        assert camelot("C", "major") == (8, "B")
        assert camelot("A", "minor") == (8, "A")
        assert camelot("G", "major") == (9, "B")
        assert camelot("F#", "minor") == (11, "A")

    def test_flat_aliases(self):
        # Essentia may report flats; Eb == D#
        assert camelot("Eb", "minor") == camelot("D#", "minor")

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            camelot("H", "major")


class TestKeyScore:
    def test_identical_key_is_perfect(self):
        assert key_score("C", "major", "C", "major") == 1.0

    def test_relative_major_minor_is_perfect(self):
        # A minor is the relative minor of C major -> same Camelot number
        assert key_score("C", "major", "A", "minor") == 1.0

    def test_adjacent_on_wheel_is_high(self):
        # C major (8B) and G major (9B) are harmonically adjacent
        assert key_score("C", "major", "G", "major") == pytest.approx(0.8)

    def test_distant_key_is_low(self):
        # C major (8B) vs F# major (2B): distance 6, the far side of the wheel
        assert key_score("C", "major", "F#", "major") < 0.3

    def test_symmetry(self):
        a = key_score("D", "minor", "Bb", "major")
        b = key_score("Bb", "major", "D", "minor")
        assert a == b


class TestBpmScore:
    def test_identical_bpm(self):
        assert bpm_score(120, 120) == pytest.approx(1.0)

    def test_close_bpm_high(self):
        assert bpm_score(120, 124) > 0.8

    def test_far_bpm_low(self):
        assert bpm_score(80, 150) < 0.3

    def test_double_time_counts_as_close(self):
        # 60 vs 120 BPM: same groove at half/double time
        assert bpm_score(60, 120) > 0.9

    def test_symmetry(self):
        assert bpm_score(93, 128) == pytest.approx(bpm_score(128, 93))


class TestEmbeddingScore:
    def test_identical_vectors(self):
        v = np.array([0.3, 0.5, 0.1])
        assert embedding_score(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert embedding_score(a, b) == pytest.approx(0.0)

    def test_zero_vector_safe(self):
        a = np.zeros(3)
        b = np.array([1.0, 2.0, 3.0])
        assert embedding_score(a, b) == 0.0


class TestConnection:
    def _track(self, name, bpm, key, scale, emb):
        return {
            "title": name,
            "bpm": bpm,
            "key": key,
            "scale": scale,
            "embedding": np.array(emb, dtype=float),
            "tags": [("pop", 0.5)],
        }

    def test_identical_tracks_score_near_one(self):
        t = self._track("a", 120, "C", "major", [0.2, 0.8, 0.4])
        result = connection(t, t)
        assert result["score"] == pytest.approx(1.0)

    def test_score_between_zero_and_one(self):
        a = self._track("a", 80, "C", "major", [1.0, 0.0])
        b = self._track("b", 178, "F#", "minor", [0.0, 1.0])
        assert 0.0 <= connection(a, b)["score"] <= 1.0

    def test_reasons_are_human_readable(self):
        a = self._track("a", 120, "C", "major", [0.2, 0.8])
        b = self._track("b", 122, "A", "minor", [0.2, 0.8])
        reasons = connection(a, b)["reasons"]
        assert any("BPM" in r for r in reasons)
        assert any("key" in r.lower() for r in reasons)

    def test_embedding_dominates_weighting(self):
        # Same audio character but different tempo/key should beat
        # same tempo/key with alien audio character.
        seed = self._track("seed", 120, "C", "major", [1.0, 0.0, 0.0])
        same_sound = self._track("sound", 90, "E", "major", [0.98, 0.1, 0.05])
        same_tempo = self._track("tempo", 120, "C", "major", [0.0, 0.0, 1.0])
        assert connection(seed, same_sound)["score"] > connection(seed, same_tempo)["score"]
