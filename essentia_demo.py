"""Essentia music analysis demo.

Fetches 30-second preview clips from the Deezer API, then analyzes each with:
  - RhythmExtractor2013  -> BPM
  - KeyExtractor         -> musical key
  - MusiCNN (TensorFlow) -> top auto-tags (genre/mood/instrumentation)

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
    TensorflowPredictMusiCNN,
)

ROOT = Path(__file__).parent
MODEL_PB = ROOT / "models" / "msd-musicnn-1.pb"
MODEL_META = ROOT / "models" / "msd-musicnn-1.json"
SAMPLES_DIR = ROOT / "samples"

DEFAULT_QUERIES = ["daft punk", "johnny cash", "bach cello suite"]


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


def analyze(mp3_path: Path, tag_labels: list[str]) -> None:
    # Classic signal analysis runs at 44.1 kHz.
    audio_44k = MonoLoader(filename=str(mp3_path), sampleRate=44100)()
    bpm, *_ = RhythmExtractor2013(method="multifeature")(audio_44k)
    key, scale, strength = KeyExtractor()(audio_44k)

    # MusiCNN expects 16 kHz input.
    audio_16k = MonoLoader(filename=str(mp3_path), sampleRate=16000)()
    activations = TensorflowPredictMusiCNN(graphFilename=str(MODEL_PB))(audio_16k)
    mean_act = activations.mean(axis=0)
    top = sorted(zip(tag_labels, mean_act), key=lambda x: -x[1])[:5]

    print(f"  BPM:  {bpm:.1f}")
    print(f"  Key:  {key} {scale} (confidence {strength:.2f})")
    print("  Tags: " + ", ".join(f"{label} ({score:.2f})" for label, score in top))


def main() -> None:
    queries = sys.argv[1:] or DEFAULT_QUERIES
    tag_labels = json.loads(MODEL_META.read_text())["classes"]
    SAMPLES_DIR.mkdir(exist_ok=True)

    for query in queries:
        print(f"\n=== {query} ===")
        mp3 = fetch_deezer_preview(query)
        if mp3:
            analyze(mp3, tag_labels)


if __name__ == "__main__":
    main()
