"""MonoLoader(44.1 kHz) + rhythm DSP -> groove vector.

Extractor choices here are open (spec §2.1) and private to this file:
change freely without breaking other lanes, as long as the output stays
a 1-D float vector matching contract FEATURE_KEYS["groove"].
"""
from __future__ import annotations

from pathlib import Path


def groove_vector(mp3_path: Path | str) -> "np.ndarray":
    """[bpm, beats_confidence, onset_rate, danceability]"""
    raise NotImplementedError
