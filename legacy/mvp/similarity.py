"""Pure similarity math: key compatibility (Camelot wheel), tempo, embeddings.

No I/O and no Essentia imports here so it stays fast to test.
"""

from __future__ import annotations

import math

import numpy as np

# Camelot wheel positions. Number = position on the wheel (1-12),
# letter = A for minor, B for major. Adjacent numbers and the A/B pair
# at the same number are harmonically compatible (DJ mixing standard).
_CAMELOT_MAJOR = {
    "B": 1, "F#": 2, "C#": 3, "G#": 4, "D#": 5, "A#": 6,
    "F": 7, "C": 8, "G": 9, "D": 10, "A": 11, "E": 12,
}
_CAMELOT_MINOR = {
    "G#": 1, "D#": 2, "A#": 3, "F": 4, "C": 5, "G": 6,
    "D": 7, "A": 8, "E": 9, "B": 10, "F#": 11, "C#": 12,
}
_FLAT_TO_SHARP = {
    "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
    "Cb": "B", "Fb": "E",
}

# Weights for the combined connection score. Embedding similarity is the
# strongest signal of "sounds alike"; tempo and key make tracks *mixable*.
W_EMBEDDING = 0.6
W_BPM = 0.2
W_KEY = 0.2


def camelot(key: str, scale: str) -> tuple[int, str]:
    """Map a musical key to its Camelot wheel position, e.g. C major -> (8, 'B')."""
    key = _FLAT_TO_SHARP.get(key, key)
    if scale == "major":
        return _CAMELOT_MAJOR[key], "B"
    return _CAMELOT_MINOR[key], "A"


def key_score(key_a: str, scale_a: str, key_b: str, scale_b: str) -> float:
    """Harmonic compatibility in [0, 1] based on Camelot wheel distance."""
    num_a, letter_a = camelot(key_a, scale_a)
    num_b, letter_b = camelot(key_b, scale_b)
    dist = min((num_a - num_b) % 12, (num_b - num_a) % 12)
    if dist == 0:
        # Same number: identical key, or relative major/minor. Both mix perfectly.
        return 1.0
    base = max(0.0, 1.0 - dist / 5.0)
    # Crossing major/minor while also moving on the wheel is a bit harsher.
    if letter_a != letter_b:
        base *= 0.75
    return base


def bpm_score(bpm_a: float, bpm_b: float) -> float:
    """Tempo compatibility in [0, 1]; half/double time counts as compatible."""
    if bpm_a <= 0 or bpm_b <= 0:
        return 0.0
    best = 0.0
    for mult in (0.5, 1.0, 2.0):
        ratio = (bpm_a * mult) / bpm_b
        # Gaussian around a perfect ratio. Half/double-time matches must be
        # much tighter: 80 vs 150 should NOT pass as "160 is close to 150".
        sigma = 0.06 if mult == 1.0 else 0.025
        best = max(best, math.exp(-((math.log(ratio)) ** 2) / (2 * sigma**2)))
    return best


def embedding_score(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity clamped to [0, 1]."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(max(0.0, np.dot(a, b) / (na * nb)))


def connection(track_a: dict, track_b: dict) -> dict:
    """Score how strongly two analyzed tracks connect, with human-readable reasons.

    Tracks are dicts with keys: bpm, key, scale, embedding, tags.
    Returns {"score": float, "reasons": [str, ...], "components": {...}}.
    """
    e = embedding_score(track_a["embedding"], track_b["embedding"])
    b = bpm_score(track_a["bpm"], track_b["bpm"])
    k = key_score(track_a["key"], track_a["scale"], track_b["key"], track_b["scale"])
    score = W_EMBEDDING * e + W_BPM * b + W_KEY * k

    reasons = []
    if e > 0.85:
        reasons.append(f"very similar sound character ({e:.0%} timbre match)")
    elif e > 0.6:
        reasons.append(f"related sound character ({e:.0%} timbre match)")
    if b > 0.8:
        reasons.append(
            f"compatible tempo ({track_a['bpm']:.0f} vs {track_b['bpm']:.0f} BPM)"
        )
    if k == 1.0:
        reasons.append(
            f"harmonically perfect key pairing "
            f"({track_a['key']} {track_a['scale']} / {track_b['key']} {track_b['scale']})"
        )
    elif k >= 0.6:
        reasons.append(
            f"compatible keys ({track_a['key']} {track_a['scale']} / "
            f"{track_b['key']} {track_b['scale']})"
        )
    shared = {t for t, s in track_a["tags"][:5] if s > 0.1} & {
        t for t, s in track_b["tags"][:5] if s > 0.1
    }
    if shared:
        reasons.append("shared style tags: " + ", ".join(sorted(shared)))

    return {
        "score": score,
        "reasons": reasons,
        "components": {"embedding": e, "bpm": b, "key": k},
    }
