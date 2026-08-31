"""Axis registry: axis id -> (feature key in the analysis dict, direction).

THE one table for adding, removing, or reweighting an axis (spec §2.2).
Labels served by GET /axes come from contract/features.py — the client
renders whatever this sends.
"""
from __future__ import annotations

AXIS_FEATURES: dict[str, tuple[str, int]] = {
    "sounds_like": ("embedding", 1),
    "mood":        ("moodtheme", 1),
    "groove":      ("groove", 1),
    "surprise":    ("embedding", -1),   # most distant by embedding cosine
}
