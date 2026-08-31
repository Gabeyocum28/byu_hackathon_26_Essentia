"""MonoLoader(16 kHz) + Discogs-EffNet -> per-frame embeddings (n, 1280)."""
from __future__ import annotations

from pathlib import Path


def effnet_frames(mp3_path: Path | str) -> "np.ndarray":
    """The one slow pass (~0.5 s). Everything downstream reuses its output."""
    raise NotImplementedError
