"""Preview downloads into audio_cache/. Signed URLs expire; retry once fresh."""
from __future__ import annotations

import os
import re
import time
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


# Deezer signs previews with an expiry in the query string itself, so whether
# a stored URL can still work is answerable locally. Measured on the live
# candidate pool, 12 of 12 queued tracks had already-dead URLs, and attempting
# each one cost a 0.10 s round trip purely to be told 403 -- 12% of the whole
# per-track network budget, spent on a certainty.
# Deezer nests it: "?hdnea=exp=1788327206~acl=/api/...", so the character
# before "exp=" is itself an "=".
_EXP = re.compile(r"\bexp=(\d+)")

# A URL about to expire is not worth attempting either: the download itself
# takes ~0.5 s, and losing that race just means paying for the re-sign anyway.
_EXPIRY_MARGIN_S = 30


def is_live(url: str | None) -> bool:
    """Whether a signed preview URL still has time on it.

    Unsigned or unparseable URLs are assumed live -- the check exists to skip
    certain failures, not to invent them.
    """
    if not url:
        return False
    m = _EXP.search(url)
    if not m:
        return True
    return int(m.group(1)) > time.time() + _EXPIRY_MARGIN_S


# The preview CDN throttles bursts independently of the API: 24 concurrent
# fetches came back 429 for every one of 60 tracks while single fetches kept
# working. A 429 is a "come back later", not a dead track, so retrying is the
# difference between a slow batch and a silently lost one -- _one_download in
# ingest.py turns any exception into a skip, so without this the track is
# simply never analyzed and nothing says so.
_RETRY_429 = 3
_BACKOFF_S = 2.0


def _fetch(url: str, dest: Path) -> bool:
    for attempt in range(_RETRY_429):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < _RETRY_429 - 1:
                time.sleep(_BACKOFF_S * (attempt + 1))
                continue
            return False
        except (urllib.error.URLError, TimeoutError):
            return False
        if len(data) < MIN_BYTES:
            return False
        dest.write_bytes(data)
        return True
    return False


def download_preview(track: dict, dest_dir: Path = AUDIO_CACHE) -> Path:
    """Download a track's preview mp3 into dest_dir, retrying with a fresh signed URL on 403.

    The stored preview_url is signed and dies in roughly 15 minutes, so on any
    long crawl most of them are already dead by the time the downloader reaches
    them. Refetching by track_id is the recovery, and it is the difference
    between a batch run that works and one that 403s halfway through.

    The expiry is in the URL, so a dead one is skipped without asking the
    network -- a freshly crawled track still downloads on the first try.

    Raises RuntimeError if neither URL yields audio, so the caller can skip the
    track and keep going.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{track['track_id']}.mp3"
    if dest.exists() and dest.stat().st_size >= MIN_BYTES:
        return dest

    # Only attempt the stored URL if its own signature says it is still valid.
    if is_live(track.get("preview_url")) and _fetch(track["preview_url"], dest):
        return dest
    fresh = deezer.fresh_preview_url(track["track_id"])
    if fresh and _fetch(fresh, dest):
        return dest
    raise RuntimeError(f"no working preview for {track['track_id']}")
