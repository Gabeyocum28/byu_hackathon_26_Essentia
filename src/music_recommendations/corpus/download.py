"""Preview downloads into audio_cache/. Signed URLs expire; retry once fresh."""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from . import deezer

AUDIO_CACHE = Path(__file__).resolve().parents[3] / "audio_cache"


def download_preview(track: dict, dest_dir: Path = AUDIO_CACHE) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{track['track_id']}.mp3"
    if path.exists():
        return path
    try:
        urllib.request.urlretrieve(track["preview_url"], path)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
        fresh = deezer.fresh_preview_url(track["track_id"])
        if not fresh:
            raise
        track["preview_url"] = fresh
        urllib.request.urlretrieve(fresh, path)
    return path
