"""Preview downloads into audio_cache/. Signed URLs expire; retry once fresh."""
from __future__ import annotations

from pathlib import Path

AUDIO_CACHE = Path(__file__).resolve().parents[3] / "audio_cache"


def download_preview(track: dict, dest_dir: Path = AUDIO_CACHE) -> Path:
    """Download a track's preview mp3 into dest_dir, retrying with a fresh signed URL on 403."""
    raise NotImplementedError
