"""Audio feature extraction with Essentia.

Per track we extract:
  - BPM (RhythmExtractor2013)
  - musical key + scale + confidence (KeyExtractor)
  - loudness proxy (RMS energy)
  - danceability (Essentia's Danceability algorithm)
  - 50 MusiCNN auto-tags (genre / mood / instrumentation)
  - a 200-dim MusiCNN embedding (penultimate layer) for timbre similarity

Analysis results are cached as JSON so re-runs are instant.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import essentia

essentia.log.infoActive = False
essentia.log.warningActive = False

from essentia.standard import (  # noqa: E402
    Danceability,
    KeyExtractor,
    MonoLoader,
    RhythmExtractor2013,
    TensorflowPredictMusiCNN,
)

ROOT = Path(__file__).parent.parent
MODEL_PB = ROOT / "models" / "msd-musicnn-1.pb"
MODEL_META = ROOT / "models" / "msd-musicnn-1.json"
CACHE_DIR = ROOT / "cache"

TAG_LABELS: list[str] = json.loads(MODEL_META.read_text())["classes"]

# Instantiated lazily and reused: model load is the expensive part.
_tagger = None
_embedder = None


def _models():
    global _tagger, _embedder
    if _tagger is None:
        _tagger = TensorflowPredictMusiCNN(graphFilename=str(MODEL_PB))
        _embedder = TensorflowPredictMusiCNN(
            graphFilename=str(MODEL_PB), output="model/dense/BiasAdd"
        )
    return _tagger, _embedder


def analyze_track(mp3_path: Path, track_id: int | str) -> dict:
    """Extract all features for one preview MP3, using the JSON cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{track_id}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        cached["embedding"] = np.array(cached["embedding"])
        cached["tags"] = [tuple(t) for t in cached["tags"]]
        return cached

    audio_44k = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
    bpm, *_ = RhythmExtractor2013(method="multifeature")(audio_44k)
    key, scale, key_conf = KeyExtractor()(audio_44k)
    dance, _ = Danceability()(audio_44k)
    rms = float(np.sqrt(np.mean(audio_44k**2)))

    tagger, embedder = _models()
    audio_16k = MonoLoader(filename=str(mp3_path), sampleRate=16000)()
    tag_act = tagger(audio_16k).mean(axis=0)
    embedding = embedder(audio_16k).mean(axis=0)

    tags = sorted(zip(TAG_LABELS, tag_act.tolist()), key=lambda x: -x[1])
    features = {
        "bpm": float(bpm),
        "key": key,
        "scale": scale,
        "key_confidence": float(key_conf),
        "danceability": float(dance),
        "rms": rms,
        "tags": [(t, round(s, 4)) for t, s in tags[:10]],
        "embedding": embedding.tolist(),
    }
    cache_file.write_text(json.dumps(features))
    features["embedding"] = np.array(features["embedding"])
    features["tags"] = [tuple(t) for t in features["tags"]]
    return features
