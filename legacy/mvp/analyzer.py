"""Audio feature extraction with Essentia.

Per track we extract:
  - BPM (RhythmExtractor2013)
  - musical key + scale + confidence (KeyExtractor)
  - loudness proxy (RMS energy)
  - Discogs-EffNet embedding (1280-dim, penultimate layer) for timbre similarity
  - Genre Discogs400 styles (400 classes) via the EffNet embedding
  - mood probabilities (happy/sad/aggressive/relaxed/danceable heads)
  - valence & arousal (emoMusic regression on MusiCNN embeddings, 1-9 scale)

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
    KeyExtractor,
    MonoLoader,
    RhythmExtractor2013,
    TensorflowPredict2D,
    TensorflowPredictEffnetDiscogs,
    TensorflowPredictMusiCNN,
)

ROOT = Path(__file__).parent.parent
MODELS = ROOT / "models"
CACHE_DIR = ROOT / "cache"

# Bump when the feature schema changes; stale cache entries are recomputed.
CACHE_VERSION = 2

GENRE_LABELS: list[str] = json.loads(
    (MODELS / "genre_discogs400-discogs-effnet-1.json").read_text()
)["classes"]

# Two-class classifier heads on the EffNet embedding.
MOOD_HEADS = {
    "happy": "mood_happy-discogs-effnet-1",
    "sad": "mood_sad-discogs-effnet-1",
    "aggressive": "mood_aggressive-discogs-effnet-1",
    "relaxed": "mood_relaxed-discogs-effnet-1",
    "danceable": "danceability-discogs-effnet-1",
}

# Instantiated lazily and reused: model load is the expensive part.
_models_cache: dict | None = None


def _models() -> dict:
    global _models_cache
    if _models_cache is None:
        moods = {}
        for label, stem in MOOD_HEADS.items():
            classes = json.loads((MODELS / f"{stem}.json").read_text())["classes"]
            positive = next(
                i for i, c in enumerate(classes) if not c.startswith(("non_", "not_"))
            )
            head = TensorflowPredict2D(
                graphFilename=str(MODELS / f"{stem}.pb"), output="model/Softmax"
            )
            moods[label] = (head, positive)
        _models_cache = {
            "effnet": TensorflowPredictEffnetDiscogs(
                graphFilename=str(MODELS / "discogs-effnet-bs64-1.pb"),
                output="PartitionedCall:1",
            ),
            "genre": TensorflowPredict2D(
                graphFilename=str(MODELS / "genre_discogs400-discogs-effnet-1.pb"),
                input="serving_default_model_Placeholder",
                output="PartitionedCall:0",
            ),
            "musicnn_embed": TensorflowPredictMusiCNN(
                graphFilename=str(MODELS / "msd-musicnn-1.pb"),
                output="model/dense/BiasAdd",
            ),
            "emomusic": TensorflowPredict2D(
                graphFilename=str(MODELS / "emomusic-msd-musicnn-2.pb"),
                output="model/Identity",
            ),
            "moods": moods,
        }
    return _models_cache


def _split_style(label: str) -> tuple[str, str]:
    """'Electronic---House' -> ('Electronic', 'House')."""
    parent, _, style = label.partition("---")
    return parent, style or parent


def _deserialize(features: dict) -> dict:
    features["embedding"] = np.array(features["embedding"])
    features["tags"] = [tuple(t) for t in features["tags"]]
    return features


def analyze_track(mp3_path: Path, track_id: int | str) -> dict:
    """Extract all features for one preview MP3, using the JSON cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{track_id}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        if cached.get("version") == CACHE_VERSION:
            return _deserialize(cached)

    audio_44k = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
    bpm, *_ = RhythmExtractor2013(method="multifeature")(audio_44k)
    key, scale, key_conf = KeyExtractor()(audio_44k)
    rms = float(np.sqrt(np.mean(audio_44k**2)))

    m = _models()
    audio_16k = MonoLoader(filename=str(mp3_path), sampleRate=16000)()

    # One EffNet pass feeds genre + every mood head; its mean is the embedding.
    effnet_frames = m["effnet"](audio_16k)
    embedding = effnet_frames.mean(axis=0)

    genre_act = m["genre"](effnet_frames).mean(axis=0)
    styles = sorted(zip(GENRE_LABELS, genre_act.tolist()), key=lambda x: -x[1])

    # Aggregate style activations by Discogs parent category for grouping.
    families: dict[str, float] = {}
    for label, score in styles:
        parent, _ = _split_style(label)
        families[parent] = families.get(parent, 0.0) + score

    mood = {
        label: float(head(effnet_frames).mean(axis=0)[positive])
        for label, (head, positive) in m["moods"].items()
    }

    emo = m["emomusic"](m["musicnn_embed"](audio_16k)).mean(axis=0)

    features = {
        "version": CACHE_VERSION,
        "bpm": float(bpm),
        "key": key,
        "scale": scale,
        "key_confidence": float(key_conf),
        "danceability": mood["danceable"],
        "rms": rms,
        "tags": [
            (_split_style(label)[1], round(score, 4)) for label, score in styles[:10]
        ],
        "genre_families": sorted(
            ((p, round(s, 4)) for p, s in families.items()), key=lambda x: -x[1]
        )[:5],
        "mood": {k: round(v, 4) for k, v in mood.items()},
        "valence": round(float(emo[0]), 2),
        "arousal": round(float(emo[1]), 2),
        "embedding": embedding.tolist(),
    }
    cache_file.write_text(json.dumps(features))
    return _deserialize(dict(features))
