"""Tests for the recommender and the Deezer client's data shaping."""

import numpy as np

from mvp.deezer import _slim
from mvp.recommend import format_recommendation, recommend


def _entry(track_id, name, bpm, key, scale, emb):
    return {
        "id": track_id,
        "title": name,
        "artist": "artist",
        "features": {
            "bpm": bpm,
            "key": key,
            "scale": scale,
            "embedding": np.array(emb, dtype=float),
            "tags": [("pop", 0.5)],
        },
    }


class TestRecommend:
    def test_excludes_seed_itself(self):
        seed = _entry(1, "seed", 120, "C", "major", [1, 0])
        library = [seed, _entry(2, "other", 120, "C", "major", [1, 0])]
        recs = recommend(seed, library)
        assert all(r["id"] != 1 for r in recs)

    def test_ranked_descending(self):
        seed = _entry(1, "seed", 120, "C", "major", [1, 0, 0])
        library = [
            seed,
            _entry(2, "far", 178, "F#", "minor", [0, 0, 1]),
            _entry(3, "close", 121, "C", "major", [0.95, 0.1, 0]),
            _entry(4, "mid", 100, "G", "major", [0.6, 0.4, 0]),
        ]
        recs = recommend(seed, library)
        scores = [r["connection"]["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        assert recs[0]["title"] == "close"

    def test_top_n_respected(self):
        seed = _entry(1, "seed", 120, "C", "major", [1, 0])
        library = [seed] + [
            _entry(i, f"t{i}", 100 + i, "D", "minor", [0.5, 0.5]) for i in range(2, 12)
        ]
        assert len(recommend(seed, library, top_n=3)) == 3

    def test_formatting_contains_score_and_reasons(self):
        seed = _entry(1, "seed", 120, "C", "major", [1, 0])
        library = [seed, _entry(2, "twin", 120, "C", "major", [1, 0])]
        text = format_recommendation(1, recommend(seed, library)[0])
        assert "score" in text
        assert "tempo" in text


class TestDeezerSlim:
    def test_slim_extracts_expected_fields(self):
        raw = {
            "id": 42,
            "title": "Song",
            "artist": {"id": 7, "name": "Band"},
            "album": {"title": "LP"},
            "duration": 200,
            "rank": 900000,
            "preview": "https://example.com/p.mp3",
            "link": "https://deezer.com/track/42",
        }
        slim = _slim(raw)
        assert slim == {
            "id": 42,
            "title": "Song",
            "artist": "Band",
            "artist_id": 7,
            "album": "LP",
            "duration": 200,
            "rank": 900000,
            "preview": "https://example.com/p.mp3",
            "link": "https://deezer.com/track/42",
        }

    def test_slim_handles_missing_optionals(self):
        raw = {"id": 1, "title": "X", "artist": {"id": 2, "name": "Y"}}
        slim = _slim(raw)
        assert slim["preview"] == ""
        assert slim["album"] == ""
