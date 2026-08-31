"""MVP demo: audio-based music connections from Deezer previews + Essentia.

Builds a genre-diverse library of 30s previews, extracts audio features and
neural embeddings for each, then prints explainable recommendations for a few
seed tracks. Saves the full analyzed library to library.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from mvp import deezer
from mvp.analyzer import analyze_track
from mvp.recommend import format_recommendation, recommend

ROOT = Path(__file__).parent
SAMPLES = ROOT / "samples"

# Deliberately diverse: the point is to see which connections the AUDIO finds,
# not which artists share fans.
LIBRARY_QUERIES = [
    "daft punk around the world",
    "justice genesis",
    "the weeknd blinding lights",
    "dua lipa levitating",
    'artist:"johnny cash" track:"hurt"',
    "chris stapleton tennessee whiskey",
    "nirvana smells like teen spirit",
    "arctic monkeys do i wanna know",
    "miles davis so what",
    "norah jones dont know why",
    "bob marley three little birds",
    "kendrick lamar humble",
    "eminem lose yourself",
    "hans zimmer time",
    "bach cello suite prelude",
    "skrillex bangarang",
    "avicii wake me up",
    'artist:"adele" track:"someone like you"',
    "billie eilish bad guy",
    "fleetwood mac dreams",
]

SEED_TITLES = ["Blinding Lights", "Hurt", "So What", "Wake Me Up"]


def build_library() -> list[dict]:
    library, seen_ids = [], set()
    for query in LIBRARY_QUERIES:
        tracks = deezer.search_tracks(query, limit=1)
        if not tracks:
            print(f"  ! no result for '{query}'")
            continue
        track = tracks[0]
        if track["id"] in seen_ids:
            continue
        seen_ids.add(track["id"])

        t0 = time.time()
        mp3 = deezer.download_preview(track, SAMPLES)
        track["features"] = analyze_track(mp3, track["id"])
        f = track["features"]
        top_tags = ", ".join(t for t, _ in f["tags"][:3])
        print(
            f"  analyzed [{time.time() - t0:4.1f}s] {track['artist']} - "
            f"{track['title'][:40]:40s} {f['bpm']:5.1f} BPM  "
            f"{f['key']:>2s} {f['scale']:5s}  [{top_tags}]"
        )
        library.append(track)
    return library


def main() -> None:
    print(f"Building library from {len(LIBRARY_QUERIES)} Deezer queries...\n")
    library = build_library()
    print(f"\nLibrary: {len(library)} tracks analyzed.\n")

    for seed_title in SEED_TITLES:
        seed = next((t for t in library if seed_title.lower() in t["title"].lower()), None)
        if seed is None:
            continue
        f = seed["features"]
        print("=" * 78)
        print(
            f"SEED: {seed['artist']} - {seed['title']}\n"
            f"      {f['bpm']:.0f} BPM, {f['key']} {f['scale']}, "
            f"danceability {f['danceability']:.1f}, "
            f"tags: {', '.join(t for t, _ in f['tags'][:4])}"
        )
        print("-" * 78)
        for i, rec in enumerate(recommend(seed, library, top_n=4), 1):
            print(format_recommendation(i, rec))
        print()

    out = ROOT / "library.json"
    serializable = [
        {**t, "features": {**t["features"], "embedding": None}} for t in library
    ]
    out.write_text(json.dumps(serializable, indent=2))
    print(f"Full metadata + features written to {out.name}")


if __name__ == "__main__":
    sys.exit(main())
