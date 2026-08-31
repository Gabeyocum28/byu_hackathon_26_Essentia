"""MonoLoader(44.1 kHz) + rhythm DSP -> groove vector.

Extractor choices here are open (spec §2.1) and private to this file:
change freely without breaking other lanes, as long as the output stays
a 1-D float vector matching contract FEATURE_KEYS["groove"].
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def groove_vector(mp3_path: Path | str) -> np.ndarray:
    """[bpm, beats_confidence, onset_rate, danceability]"""
    from essentia.standard import (
        Danceability,
        MonoLoader,
        OnsetRate,
        RhythmExtractor2013,
    )

    audio = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
    bpm, _, beats_conf, _, _ = RhythmExtractor2013(method="multifeature")(audio)
    onset_rate = float(OnsetRate()(audio)[1])
    dance = float(Danceability()(audio)[0])
    return np.array([float(bpm), float(beats_conf), onset_rate, dance])
