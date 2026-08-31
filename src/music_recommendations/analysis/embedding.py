"""MonoLoader(16 kHz) + Discogs-EffNet -> per-frame embeddings (n, 1280)."""
from __future__ import annotations

from pathlib import Path

from .registry import EFFNET_FILE, EFFNET_OUTPUT, MODELS_DIR

_effnet = None


def effnet_frames(mp3_path: Path | str):
    """The one slow pass (~0.5 s). Everything downstream reuses its output."""
    global _effnet
    from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs

    if _effnet is None:
        _effnet = TensorflowPredictEffnetDiscogs(
            graphFilename=str(MODELS_DIR / EFFNET_FILE), output=EFFNET_OUTPUT
        )
    audio = MonoLoader(filename=str(mp3_path), sampleRate=16000)()
    return _effnet(audio)
