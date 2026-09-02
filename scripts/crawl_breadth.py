"""Widen the candidate pool across the whole catalogue, not deeper into it.

Measured on a 2,586-track sample of the existing corpus, three broad genres
were 62% of everything (Hip Hop 24%, Electronic 20%, Rock 19%) while Classical
was 2.7%, Blues 1.2% and 161 of the 400 Discogs styles had no tracks at all.
That is what the existing crawlers produce by construction:

  snowball()  starts from 8 jazz artists and explores one neighbourhood.
  deep_cuts() pulls album tracks from artists ALREADY in the pool, so it
              deepens whatever skew is already there.
  from_charts() is the broad one, but it was wired to 17 genre ids when
              Deezer exposes 28 -- Asian, Indian, Christian, Salsa, Cumbia,
              Traditional Mexicano, Films/Games, Kids, Reggaeton and Latin
              were never crawled.

So: start from EVERY Deezer genre, then snowball outward from each genre's
own chart artists, round-robin, with a per-genre cap. Round-robin is the
point -- crawling genres in sequence and stopping when time runs out just
means the last genres never happen, which is how a skew is born.

  python3 scripts/crawl_breadth.py                      # merge into the pool
  python3 scripts/crawl_breadth.py --per-genre 4000     # bigger target
  python3 scripts/crawl_breadth.py --hops 3             # further out

Flushes every FLUSH_EVERY new tracks and merges with whatever is already in
corpus_candidates.json, so it is safe to kill at any point and safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
from music_recommendations.corpus import deezer  # noqa: E402

OUT = _ROOT / "corpus_candidates.json"
FLUSH_EVERY = 300

# 17.8% of the corpus measured as redundant -- the same song under many track
# ids ("Rasputin" 15 times), because Deezer lists every compilation and
# remaster separately. Suppressing them at crawl time is the cheap end: the
# alternative is paying to analyze 16k copies and filtering later.
_PAREN = re.compile(
    r"\((?:[^)]*(?:remaster|remix|live|version|edit|mix|mono|stereo|deluxe"
    r"|radio|explicit|feat\.?|bonus)[^)]*)\)", re.I)
_DASH = re.compile(r"\s*-\s*[^-]*(?:remaster|remix|live|version|edit|mix)[^-]*$", re.I)


def song_key(track: dict) -> tuple[str, str]:
    """artist + title stripped of release variation, for duplicate detection.

    Keeps non-Latin word characters: an ascii-only strip collapses every
    Korean and Japanese title onto the same empty key, which reads as a pile
    of false duplicates.
    """
    title = unicodedata.normalize("NFKC", track["title"])
    title = _DASH.sub("", _PAREN.sub("", title))
    title = re.sub(r"[^\w]+", "", title, flags=re.UNICODE).lower()
    return (track["artist"].lower(), title)


def all_genres() -> dict[int, str]:
    """Every genre Deezer lists, rather than the 17 hardcoded in crawl.py."""
    with urllib.request.urlopen("https://api.deezer.com/genre", timeout=15) as r:
        data = json.load(r)["data"]
    return {g["id"]: g["name"] for g in data if g["id"] != 0}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return {t["track_id"]: t for t in json.loads(path.read_text())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-genre", type=int, default=3000,
                    help="stop widening a genre once it has contributed this many NEW tracks")
    ap.add_argument("--hops", type=int, default=2,
                    help="how far to snowball off each genre's chart artists")
    ap.add_argument("--per-artist", type=int, default=20)
    ap.add_argument("--max-per-artist", type=int, default=8,
                    help="cap tracks kept per artist -- breadth comes from "
                         "many artists, not many tracks by a few")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    pool = _load(args.out)
    start = len(pool)
    # Everything already known, so the crawl adds only genuinely new material
    # rather than re-finding the corpus it already has.
    seen_songs = {song_key(t) for t in pool.values()}
    per_artist = defaultdict(int)
    for t in pool.values():
        per_artist[t["artist"].lower()] += 1
    print(f"{start} candidates already in {args.out.name}; "
          f"{len(seen_songs)} distinct songs, {len(per_artist)} artists", flush=True)

    def offer(track: dict) -> bool:
        """Add a track unless it duplicates a song or over-fills one artist."""
        if track["track_id"] in pool:
            return False
        key = song_key(track)
        if key in seen_songs:
            return False
        artist = track["artist"].lower()
        if per_artist[artist] >= args.max_per_artist:
            return False
        pool[track["track_id"]] = track
        seen_songs.add(key)
        per_artist[artist] += 1
        return True

    genres = all_genres()
    print(f"{len(genres)} Deezer genres: {', '.join(genres.values())}\n", flush=True)

    # Per genre: a frontier of artists to expand, and a count of what it added.
    frontier: dict[int, deque] = {}
    seen_artists: set[int] = set()
    added = defaultdict(int)

    for gid, name in genres.items():
        q = deque()
        try:
            # One chart call, used for both the tracks and the seed artists --
            # every Deezer call costs 0.2 s against a shared rate limiter, so
            # fetching the same chart twice doubles the seeding phase.
            chart = deezer.chart_tracks(gid, limit=100)
            for track in chart:
                if offer(track):
                    added[gid] += 1
            # chart_tracks gives contract Tracks, not artist ids, so the
            # frontier is seeded by resolving the chart's artist names once.
            names = list(dict.fromkeys(t["artist"] for t in chart))[:25]
            for artist_name in names:
                a = deezer.search_artist(artist_name)
                if a and a["id"] not in seen_artists:
                    seen_artists.add(a["id"])
                    q.append((a["id"], 0))
        except Exception as exc:
            print(f"  {name}: chart failed ({exc})", flush=True)
        frontier[gid] = q
        print(f"  {name:24} seeded {len(q):3d} artists, +{added[gid]} chart tracks",
              flush=True)

    print("\nsnowballing round-robin across genres...\n", flush=True)
    since_flush = 0
    live = [g for g in genres if frontier[g]]
    while live:
        random.shuffle(live)
        for gid in list(live):
            q = frontier[gid]
            if not q or added[gid] >= args.per_genre:
                live.remove(gid)
                continue
            artist_id, hop = q.popleft()
            try:
                for track in deezer.artist_top_tracks(artist_id, limit=args.per_artist):
                    if offer(track):
                        added[gid] += 1
                        since_flush += 1
                if hop < args.hops:
                    for rel in deezer.related_artists(artist_id, limit=args.per_artist):
                        if rel["id"] not in seen_artists:
                            seen_artists.add(rel["id"])
                            q.append((rel["id"], hop + 1))
            except Exception:
                continue    # one dead artist must not end the crawl
            if since_flush >= FLUSH_EVERY:
                args.out.write_text(json.dumps(list(pool.values()), indent=1))
                since_flush = 0
                total = len(pool) - start
                print(f"  {len(pool)} candidates (+{total})  " +
                      "  ".join(f"{genres[g][:9]}:{added[g]}"
                                for g in sorted(added, key=added.get, reverse=True)[:6]),
                      flush=True)

    args.out.write_text(json.dumps(list(pool.values()), indent=1))
    print(f"\n{len(pool)} candidates (+{len(pool)-start} new)")
    for g in sorted(added, key=added.get, reverse=True):
        print(f"  {genres[g]:24} +{added[g]}")


if __name__ == "__main__":
    main()
