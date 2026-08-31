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
   bpm 68-172, confidence 0.4-4.0, onset rate 0.3-6.7 and danceability
   0.8-2.0, so without rescaling any distance metric is mostly "compare the
   bpm". The dict shape is unchanged, which is all the contract fixes
   (spec §7).

3. Tempo is NOT folded into an octave, though it was until v2 and spec §10
   suggests folding as the fix for tempo octave errors. Measured on a
   150-track pool: folding moved 66 of 150 tracks and doubled none, and it
   caused more damage than the risk it guarded. Judas Priest at 163 BPM
   folded to 81.6 and collided with a track genuinely at 84, scoring 0.92 —
   they share nothing rhythmically. Unfolded, that pair drops to 0.66 while
   genuinely-matched pairs hold (Ozzy/Bluesbreakers, both ~137, 0.94 ->
   0.93). No octave error was actually observed in that sample.

Known limit: four rhythm scalars cannot separate a Mozart clarinet quintet
from a hardcore track when both sit at ~152 BPM with similar onset density.
That pair scores 0.85 and no amount of rescaling fixes it, because nothing
here describes timbre. Groove is a rhythm axis, and the honest version of
its promise is "similar tempo and pulse", not "similar-sounding".
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

# Each range brackets what was measured across a 150-track pool drawn from 17
# Deezer genre charts, with headroom so a broader corpus clips rarely. They are
# deliberately FIXED rather than corpus min/max: analyze_track is a pure
# per-track function and cannot see the corpus. Corpus-relative standardization
# would discriminate slightly better (86% top-5 agreement with this), but it
# would have to happen at rank time, which is another lane.
#
# The point of matching the ranges is that every dimension gets a comparable
# say. Before this, tempo had std 0.31 and danceability 0.08, so the distance
# was mostly tempo and danceability barely voted.
TEMPO_LO, TEMPO_HI = 55.0, 210.0    # measured 67.8-172.3
MAX_BEATS_CONFIDENCE = 4.5          # measured 0.40-4.04 (docs claim 0-5.32)
MAX_ONSET_RATE = 7.0                # measured 0.33-6.70, onsets/sec
DANCE_LO, DANCE_HI = 0.5, 2.5       # measured 0.76-2.04


def _scale(value: float, lo: float, hi: float) -> float:
    """Map [lo, hi] onto [0, 1], clamped."""
    if not np.isfinite(value):
        return 0.0
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def _tempo_feature(bpm: float) -> float:
    """Tempo on a log scale -> [0, 1]. Log because tempo is perceived that way."""
    if not np.isfinite(bpm) or bpm <= 0:
        return 0.0
    return _scale(float(np.log2(bpm)), np.log2(TEMPO_LO), np.log2(TEMPO_HI))


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
        "beats_confidence": float(beats_confidence),
        "onset_rate": float(onset_rate),
        "danceability": float(danceability),
    }


def normalize(raw: dict) -> np.ndarray:
    """Raw measurements -> the 4-float contract vector, each in [0, 1]."""
    return np.array(
        [
            _tempo_feature(raw["bpm"]),
            _scale(raw["beats_confidence"], 0.0, MAX_BEATS_CONFIDENCE),
            _scale(raw["onset_rate"], 0.0, MAX_ONSET_RATE),
            _scale(raw["danceability"], DANCE_LO, DANCE_HI),
        ],
        dtype=float,
    )


def groove_vector(mp3_path: Path | str) -> np.ndarray:
    """[bpm, beats_confidence, onset_rate, danceability], each normalized."""
    return normalize(groove_raw(mp3_path))
