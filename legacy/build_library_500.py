"""Build a large library from Deezer genre charts and analyze every track.

Pulls the top-100 chart from a spread of Deezer genres, interleaves them
round-robin (so the library stays genre-diverse even if it stops early),
dedupes, and analyzes up to TARGET tracks. Progress is saved to library.json
every SAVE_EVERY tracks, so a partial run still exports a usable graph.

Usage:
    python3 build_library_500.py            # 500 tracks
    python3 build_library_500.py 120        # smaller run
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from mvp import deezer
from mvp.analyzer import analyze_track

ROOT = Path(__file__).parent
SAMPLES = ROOT / "samples"
OUT = ROOT / "library.json"

SAVE_EVERY = 25

# Deezer genre id -> name, chosen for audible diversity.
GENRES = {
    132: "Pop",
    116: "Rap/Hip Hop",
    152: "Rock",
    113: "Dance",
    106: "Electro",
    85: "Alternative",
    165: "R&B",
    129: "Jazz",
    98: "Classical",
    84: "Country",
    466: "Folk",
    144: "Reggae",
    464: "Metal",
    169: "Soul & Funk",
    153: "Blues",
    173: "Films/Games",
    197: "Latin Music",
    122: "Reggaeton",
}


def fetch_candidates() -> list[dict]:
    """Chart tracks from every genre, interleaved round-robin, deduped."""
    per_genre: list[list[dict]] = []
    for gid, name in GENRES.items():
        try:
            data = deezer._get(f"/chart/{gid}/tracks", limit=100).get("data", [])
        except Exception as exc:
            print(f"  ! chart fetch failed for {name}: {exc}")
            continue
        tracks = [deezer._slim(t) for t in data if t.get("preview")]
        for t in tracks:
            t["chart_genre"] = name
        per_genre.append(tracks)
        print(f"  chart {name:20s} {len(tracks)} tracks")
        time.sleep(0.15)  # stay well under Deezer's rate limit

    seen: set[int] = set()
    interleaved: list[dict] = []
    for i in range(max(len(g) for g in per_genre)):
        for tracks in per_genre:
            if i < len(tracks) and tracks[i]["id"] not in seen:
                seen.add(tracks[i]["id"])
                interleaved.append(tracks[i])
    return interleaved


def save(library: list[dict]) -> None:
    serializable = [
        {**t, "features": {**t["features"], "embedding": None}} for t in library
    ]
    OUT.write_text(json.dumps(serializable, indent=2))


def main() -> None:
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    candidates = fetch_candidates()
    print(f"\n{len(candidates)} unique candidates; analyzing up to {target}\n")

    library: list[dict] = []
    t_start = time.time()
    for track in candidates:
        if len(library) >= target:
            break
        try:
            t0 = time.time()
            mp3 = deezer.download_preview(track, SAMPLES)
            track["features"] = analyze_track(mp3, track["id"])
        except Exception as exc:
            print(f"  ! skipped {track['artist']} - {track['title'][:40]}: {exc}")
            continue
        library.append(track)
        n = len(library)
        if n % 10 == 0:
            rate = (time.time() - t_start) / n
            eta = (target - n) * rate / 60
            print(
                f"  {n:4d}/{target}  [{time.time() - t0:4.1f}s] "
                f"{track['chart_genre']:14s} {track['artist'][:24]:24s} "
                f"eta {eta:4.1f} min"
            )
        if n % SAVE_EVERY == 0:
            save(library)

    save(library)
    print(
        f"\nDone: {len(library)} tracks analyzed in "
        f"{(time.time() - t_start) / 60:.1f} min -> {OUT.name}"
    )


if __name__ == "__main__":
    main()
