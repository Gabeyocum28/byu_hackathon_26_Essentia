"""Build contract/fixture.json: 30 real jazz tracks from the 8 root artists.

Operator entry point — run once at hour 0, then fixture.json is frozen.
Usage: python3 scripts/build_fixture.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.corpus import deezer
from music_recommendations.corpus.crawl import ROOTS

OUT = Path(__file__).resolve().parents[1] / "contract" / "fixture.json"
TARGET = 30


def main() -> None:
    tracks: dict[str, dict] = {}
    for name in ROOTS:
        artist = deezer.search_artist(name)
        if not artist:
            continue
        for t in deezer.artist_top_tracks(artist["id"], limit=5):
            tracks.setdefault(t["track_id"], t)
            if len(tracks) >= TARGET:
                break
        if len(tracks) >= TARGET:
            break
    if len(tracks) < TARGET:
        sys.exit(f"only found {len(tracks)} tracks; wanted {TARGET}")
    OUT.write_text(json.dumps({"tracks": list(tracks.values())[:TARGET]}, indent=2))
    print(f"wrote {TARGET} tracks -> {OUT}")


if __name__ == "__main__":
    main()
