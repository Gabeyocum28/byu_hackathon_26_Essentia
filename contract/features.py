"""The shared shapes: Track fields, axis list, and what analyze_track returns.

This file is data, not logic. It is read-only (see CLAUDE.md).
"""
from __future__ import annotations

# Every Track object at every endpoint has exactly these keys.
# "score" additionally appears on recommendation results only.
TRACK_FIELDS = frozenset(
    {"track_id", "title", "artist", "album", "artwork_url", "preview_url"}
)

# GET /axes returns exactly this, in this order.
AXES = [
    {"id": "sounds_like", "label": "Sounds like this"},
    {"id": "mood",        "label": "Keep the feeling"},
    {"id": "genre",       "label": "Keep the style"},
    {"id": "groove",      "label": "Keep the groove"},
    {"id": "surprise",    "label": "Surprise me"},
]

# analyze_track(mp3_path) -> dict with exactly these keys.
# Arrays are 1-D float lists/ndarrays of the stated length; scalars are float.
FEATURE_KEYS = {
    "embedding": 1280,   # EffNet penultimate, frame-mean
    "genre": 400,        # genre_discogs400 head activations
    "moodtheme": 56,     # mtg_jamendo_moodtheme sigmoid activations
    "mood_happy": 1, "mood_sad": 1, "mood_relaxed": 1, "mood_aggressive": 1,
    "groove": 4,         # [bpm, beats_confidence, onset_rate, danceability]
}
