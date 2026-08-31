"""Essentia music analysis demo.

Fetches 30-second preview clips from the Deezer API, then analyzes each with:
  - RhythmExtractor2013            -> BPM
  - KeyExtractor                   -> musical key
  - Discogs-EffNet embeddings feeding:
      - Genre Discogs400           -> top styles (400 classes)
      - mood/danceability heads    -> probabilities
  - MusiCNN embeddings feeding:
      - emoMusic regression        -> valence & arousal (1-9 scale)

Usage:
    python3 essentia_demo.py                      # default sample queries
    python3 essentia_demo.py "queen" "miles davis"
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Silence essentia's INFO logging before importing the algorithms.
import essentia

essentia.log.infoActive = False

from essentia.standard import (
    KeyExtractor,
    MonoLoader,
    RhythmExtractor2013,
    TensorflowPredict2D,
    TensorflowPredictEffnetDiscogs,
    TensorflowPredictMusiCNN,
)

ROOT = Path(__file__).parent
MODELS_DIR = ROOT / "models"
SAMPLES_DIR = ROOT / "samples"

EFFNET_PB = MODELS_DIR / "discogs-effnet-bs64-1.pb"
GENRE_PB = MODELS_DIR / "genre_discogs400-discogs-effnet-1.pb"
GENRE_META = MODELS_DIR / "genre_discogs400-discogs-effnet-1.json"
MUSICNN_PB = MODELS_DIR / "msd-musicnn-1.pb"
EMOMUSIC_PB = MODELS_DIR / "emomusic-msd-musicnn-2.pb"

# Two-class heads on Discogs-EffNet embeddings (label shown -> model file stem).
MOOD_MODELS = {
    "happy": "mood_happy-discogs-effnet-1",
    "sad": "mood_sad-discogs-effnet-1",
    "aggressive": "mood_aggressive-discogs-effnet-1",
    "relaxed": "mood_relaxed-discogs-effnet-1",
    "danceable": "danceability-discogs-effnet-1",
}

DEFAULT_QUERIES = [
    "daft punk",
    "johnny cash",
    "bach cello suite",
    "queen bohemian rhapsody",
    "miles davis so what",
    "kendrick lamar",
    'artist:"bob marley" track:"three little birds"',
    'artist:"metallica" track:"enter sandman"',
    "taylor swift",
    "avicii",
]


def fetch_deezer_preview(query: str) -> Path | None:
    """Search Deezer and download the first result's 30s preview MP3."""
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode(
        {"q": query, "limit": 5}
    )
    with urllib.request.urlopen(url) as resp:
        results = json.load(resp)["data"]

    track = next((t for t in results if t.get("preview")), None)
    if track is None:
        print(f"  no preview available for '{query}'")
        return None

    name = f"{track['artist']['name']} - {track['title']}"
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    path = SAMPLES_DIR / f"{safe}.mp3"
    if not path.exists():
        urllib.request.urlretrieve(track["preview"], path)
    print(f"  track: {name}")
    return path


class Analyzer:
    """Loads all models once; call analyze() per track."""

    def __init__(self) -> None:
        self.rhythm = RhythmExtractor2013(method="multifeature")
        self.key = KeyExtractor()
        self.effnet = TensorflowPredictEffnetDiscogs(
            graphFilename=str(EFFNET_PB), output="PartitionedCall:1"
        )
        self.genre = TensorflowPredict2D(
            graphFilename=str(GENRE_PB),
            input="serving_default_model_Placeholder",
            output="PartitionedCall:0",
        )
        self.genre_labels = json.loads(GENRE_META.read_text())["classes"]
        self.musicnn = TensorflowPredictMusiCNN(
            graphFilename=str(MUSICNN_PB), output="model/dense/BiasAdd"
        )
        self.emomusic = TensorflowPredict2D(
            graphFilename=str(EMOMUSIC_PB), output="model/Identity"
        )
        self.moods = {}
        for label, stem in MOOD_MODELS.items():
            classes = json.loads((MODELS_DIR / f"{stem}.json").read_text())["classes"]
            positive = next(
                i for i, c in enumerate(classes) if not c.startswith(("non_", "not_"))
            )
            head = TensorflowPredict2D(
                graphFilename=str(MODELS_DIR / f"{stem}.pb"), output="model/Softmax"
            )
            self.moods[label] = (head, positive)

    def analyze(self, mp3_path: Path) -> None:
        # Classic signal analysis runs at 44.1 kHz.
        audio_44k = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
        bpm, *_ = self.rhythm(audio_44k)
        key, scale, strength = self.key(audio_44k)

        # All TensorFlow models take 16 kHz input.
        audio_16k = MonoLoader(filename=str(mp3_path), sampleRate=16000)()

        # One EffNet embedding pass feeds genre + all mood heads.
        embeddings = self.effnet(audio_16k)

        genre_act = self.genre(embeddings).mean(axis=0)
        top_genres = sorted(
            zip(self.genre_labels, genre_act), key=lambda x: -x[1]
        )[:5]

        mood_scores = {
            label: float(head(embeddings).mean(axis=0)[positive])
            for label, (head, positive) in self.moods.items()
        }

        # emoMusic valence/arousal regression on MusiCNN embeddings (1-9 scale).
        emo = self.emomusic(self.musicnn(audio_16k)).mean(axis=0)
        valence, arousal = float(emo[0]), float(emo[1])

        print(f"  BPM:     {bpm:.1f}")
        print(f"  Key:     {key} {scale} (confidence {strength:.2f})")
        print("  Genre:   " + ", ".join(f"{g} ({s:.2f})" for g, s in top_genres))
        print("  Mood:    " + ", ".join(f"{l} ({s:.2f})" for l, s in mood_scores.items()))
        print(f"  Emotion: valence {valence:.1f}/9, arousal {arousal:.1f}/9")


def main() -> None:
    queries = sys.argv[1:] or DEFAULT_QUERIES
    SAMPLES_DIR.mkdir(exist_ok=True)
    analyzer = Analyzer()

    for query in queries:
        print(f"\n=== {query} ===")
        mp3 = fetch_deezer_preview(query)
        if mp3:
            analyzer.analyze(mp3)


if __name__ == "__main__":
    main()
