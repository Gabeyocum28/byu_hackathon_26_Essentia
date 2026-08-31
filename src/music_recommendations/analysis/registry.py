"""One table of classification heads: file, size, verified node names.

Node names are NOT uniform across heads (spec §2.1) — every head added
here must have its names checked against the actual graph, not assumed.
fetch_models.py and heads.py both read this table; adding an axis that
rides on the embedding is a one-row diff here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"

EFFNET_FILE = "discogs-effnet-bs64-1.pb"
EFFNET_URL = (
    "https://essentia.upf.edu/models/feature-extractors/discogs-effnet/"
    + EFFNET_FILE
)
EFFNET_OUTPUT = "PartitionedCall:1"  # penultimate layer -> (n_frames, 1280)


@dataclass(frozen=True)
class Head:
    filename: str      # e.g. "genre_discogs400-discogs-effnet-1.pb"
    n_out: int
    input_node: str    # verified per head; TensorflowPredict2D default lies
    output_node: str


HEADS: dict[str, Head] = {
    "genre":           Head("genre_discogs400-discogs-effnet-1.pb", 400,
                            "serving_default_model_Placeholder", "PartitionedCall:0"),
    "moodtheme":       Head("mtg_jamendo_moodtheme-discogs-effnet-1.pb", 56,
                            "model/Placeholder", "model/Sigmoid"),
    "mood_happy":      Head("mood_happy-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_sad":        Head("mood_sad-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_relaxed":    Head("mood_relaxed-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
    "mood_aggressive": Head("mood_aggressive-discogs-effnet-1.pb", 2,
                            "model/Placeholder", "model/Softmax"),
}


def model_url(filename: str) -> str:
    family = filename.split("-")[0]
    return f"https://essentia.upf.edu/models/classification-heads/{family}/{filename}"
