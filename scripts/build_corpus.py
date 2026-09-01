"""Crawl candidate tracks and save them for analysis.

Usage:
  python3 scripts/build_corpus.py                 charts, all genres  -> corpus_candidates.json
  python3 scripts/build_corpus.py --snowball      artist graph from the 8 jazz roots
  python3 scripts/build_corpus.py --snowball --hops 3
  python3 scripts/build_corpus.py --per-genre 50

Writes contract-shaped Track dicts. Crawling only -- no downloads, no
analysis, no Redis. Run analyze_corpus.py next.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.corpus import crawl  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "corpus_candidates.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snowball", action="store_true",
                        help="crawl the artist-relatedness graph instead of charts")
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--per-genre", type=int, default=100)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    if args.snowball:
        print(f"snowballing {args.hops} hops from {len(crawl.ROOTS)} roots...")
        tracks = crawl.snowball(hops=args.hops)
    else:
        print(f"crawling {len(crawl.GENRES)} genre charts...")
        tracks = crawl.from_charts(per_genre=args.per_genre)

    if not tracks:
        sys.exit("no candidates found — Deezer may be rate limiting; try again")

    existing = {}
    if args.out.exists():
        existing = {t["track_id"]: t for t in json.loads(args.out.read_text())}
    before = len(existing)
    for track in tracks:
        existing.setdefault(track["track_id"], track)

    args.out.write_text(json.dumps(list(existing.values()), indent=1))
    artists = len({t["artist"] for t in existing.values()})
    print(f"{len(existing)} candidates ({len(existing) - before} new) "
          f"from {artists} artists -> {args.out}")


if __name__ == "__main__":
    main()
