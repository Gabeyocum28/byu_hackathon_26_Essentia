"""MonoLoader(44.1 kHz) + rhythm DSP -> groove vector.

Extractor choices here are open (spec §2.1) and private to this file:
change freely without breaking other lanes, as long as the output stays
a 1-D float vector matching contract FEATURE_KEYS["groove"].

Two choices worth knowing about:

1. `danceability` is the DSP algorithm, NOT the danceability-discogs-effnet
   head the legacy MVP used. Groove is the only axis independent of the
   embedding (spec §4); sourcing a quarter of it from the embedding would
   throw away the one property that makes the fifth button mean anything.

2. The four values are normalized to roughly [0, 1] here. Raw, they span
   bpm 60-200, confidence 0-5.32, onset rate 1-20, danceability 0-3, so any
   distance metric collapses to "compare the bpm" — and bpm is exactly the
   value the spec warns halves and doubles. Tempo is folded into a single
   octave first for the same reason. The dict shape is unchanged, which is
   all the contract fixes (spec §7).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

import essentia

essentia.log.infoActive = False
essentia.log.warningActive = False

from essentia.standard import (  # noqa: E402
    Danceability,
    MonoLoader,
    OnsetRate,
    RhythmExtractor2013,
)

SAMPLE_RATE = 44100

# RhythmExtractor2013's confidence is documented on a 0-5.32 scale.
MAX_BEATS_CONFIDENCE = 5.32
# Onsets per second. Measured across the fixture: 1.8 (ballads) to 5.2 (bebop).
# 20 was the theoretical ceiling and squashed the whole corpus into 0.09-0.26.
MAX_ONSET_RATE = 8.0
# Danceability is unbounded in principle but sits in [0, 3] in practice.
MAX_DANCEABILITY = 3.0

FOLD_LOW = 60.0  # tempo octave is [60, 120)


def fold_tempo(bpm: float) -> float:
    """Collapse a tempo into [60, 120) so 68 and 136 BPM land together."""
    if not np.isfinite(bpm) or bpm <= 0:
        return FOLD_LOW
    while bpm >= FOLD_LOW * 2:
        bpm /= 2
    while bpm < FOLD_LOW:
        bpm *= 2
    return bpm


def _tempo_feature(bpm: float) -> float:
    """Folded tempo on a log scale -> [0, 1). Log because tempo is perceived so."""
    return float(np.log2(fold_tempo(bpm) / FOLD_LOW))


def groove_raw(mp3_path: Path | str) -> dict:
    """The unnormalized measurements. One decode, one pass over the audio."""
    audio = MonoLoader(filename=str(mp3_path), sampleRate=SAMPLE_RATE)()

    bpm, _ticks, beats_confidence, _estimates, _intervals = RhythmExtractor2013(
        method="multifeature"
    )(audio)
    _onsets, onset_rate = OnsetRate()(audio)
    danceability, _dfa = Danceability()(audio)

    return {
        "bpm": float(bpm),
        "bpm_folded": fold_tempo(float(bpm)),
        "beats_confidence": float(beats_confidence),
        "onset_rate": float(onset_rate),
        "danceability": float(danceability),
    }


def normalize(raw: dict) -> np.ndarray:
    """Raw measurements -> the 4-float contract vector, each roughly [0, 1]."""
    return np.array(
        [
            _tempo_feature(raw["bpm"]),
            min(raw["beats_confidence"] / MAX_BEATS_CONFIDENCE, 1.0),
            min(raw["onset_rate"] / MAX_ONSET_RATE, 1.0),
            min(raw["danceability"] / MAX_DANCEABILITY, 1.0),
        ],
        dtype=float,
    )


def groove_vector(mp3_path: Path | str) -> np.ndarray:
    """[bpm, beats_confidence, onset_rate, danceability], each normalized."""
    return normalize(groove_raw(mp3_path))
