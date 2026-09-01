"""MonoLoader(16 kHz) + Discogs-EffNet -> per-frame embeddings (n, 1280)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

import essentia

essentia.log.infoActive = False
essentia.log.warningActive = False

from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs  # noqa: E402

from . import registry  # noqa: E402

SAMPLE_RATE = 16000

# Loading the graph is the expensive part, so the model is built once and
# reused for every track. Inference itself is ~0.5 s per 30 s preview.
_effnet = None


def _model() -> TensorflowPredictEffnetDiscogs:
    global _effnet
    if _effnet is None:
        path = registry.MODELS_DIR / registry.EFFNET_FILE
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing — run: python scripts/fetch_models.py"
            )
        _effnet = TensorflowPredictEffnetDiscogs(
            graphFilename=str(path), output=registry.EFFNET_OUTPUT
        )
    return _effnet


def load_audio(mp3_path: Path | str) -> np.ndarray:
    """Decode to mono 16 kHz — the only rate EffNet accepts."""
    return MonoLoader(filename=str(mp3_path), sampleRate=SAMPLE_RATE)()


def effnet_frames(mp3_path: Path | str) -> np.ndarray:
    """The one slow pass (~0.5 s). Everything downstream reuses its output."""
    return _model()(load_audio(mp3_path))
