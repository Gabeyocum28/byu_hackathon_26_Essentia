"""Preview downloads into audio_cache/. Signed URLs expire; retry once fresh."""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

from music_recommendations.corpus import deezer

# Overridable because the repo may live somewhere that syncs: a few thousand
# previews is several GB, and iCloud does not read .gitignore. Point
# AUDIO_CACHE_DIR somewhere local before a large run.
AUDIO_CACHE = Path(
    os.environ.get("AUDIO_CACHE_DIR")
    or Path(__file__).resolve().parents[3] / "audio_cache"
).expanduser()
TIMEOUT = 45
MIN_BYTES = 10_000  # anything smaller is an error page, not 30s of audio


def _fetch(url: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError):
        return False
    if len(data) < MIN_BYTES:
        return False
    dest.write_bytes(data)
    return True


def download_preview(track: dict, dest_dir: Path = AUDIO_CACHE) -> Path:
    """Download a track's preview mp3 into dest_dir, retrying with a fresh signed URL on 403.

    The stored preview_url is signed and dies in roughly 15 minutes, so on any
    long crawl most of them are already dead by the time the downloader reaches
    them. Refetching by track_id is the recovery, and it is the difference
    between a batch run that works and one that 403s halfway through.

    Raises RuntimeError if neither URL yields audio, so the caller can skip the
    track and keep going.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{track['track_id']}.mp3"
    if dest.exists() and dest.stat().st_size >= MIN_BYTES:
        return dest

    if track.get("preview_url") and _fetch(track["preview_url"], dest):
        return dest
    fresh = deezer.fresh_preview_url(track["track_id"])
    if fresh and _fetch(fresh, dest):
        return dest
    raise RuntimeError(f"no working preview for {track['track_id']}")
