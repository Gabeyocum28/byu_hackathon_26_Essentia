"""Move an analyzed corpus between machines.

The crawler and the server do not have to run on the same Mac, but Redis is
where they meet, and Redis does not leave the machine it runs on. This carries
the analyzed corpus across as a file.

  Machine A (has the corpus):
    python3 scripts/export_corpus.py                -> corpus_export.json.gz

  Machine B (runs the server):
    python3 scripts/export_corpus.py --load corpus_export.json.gz

Loading MERGES. Tracks already on the target keep whatever they have, so
importing never destroys a corpus the other machine analyzed itself; pass
--overwrite to take the incoming copy instead.

Only analyzed tracks travel: a track:{id} without its features:{id} is not
useful to /recommend, so it is skipped rather than shipped half-formed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.server import store  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "corpus_export.json.gz"


def export(path: Path) -> int:
    """Write every analyzed track to a gzipped JSON file."""
    ids = store.corpus_ids()
    rows = []
    for index, track_id in enumerate(ids, 1):
        track = store.get_track(track_id)
        features = store.get_features(track_id)
        if not track or not features:
            continue  # half a track helps nobody
        rows.append({"track": track, "features": features})
        if index % 250 == 0:
            print(f"  read {index}/{len(ids)}")

    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(rows, handle)
    return len(rows)


def load(path: Path, overwrite: bool = False) -> tuple[int, int]:
    """Merge an exported corpus into this machine's Redis."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rows = json.load(handle)

    existing = set(store.corpus_ids())
    added = skipped = 0
    for index, row in enumerate(rows, 1):
        track_id = row["track"]["track_id"]
        if track_id in existing and not overwrite:
            skipped += 1
            continue
        store.put_track(row["track"], row["features"])
        added += 1
        if index % 250 == 0:
            print(f"  wrote {index}/{len(rows)}")
    return added, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", type=Path, metavar="FILE",
                        help="import a corpus export into this machine's Redis")
    parser.add_argument("--overwrite", action="store_true",
                        help="on load, replace tracks this machine already has")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    try:
        if args.load:
            added, skipped = load(args.load, overwrite=args.overwrite)
            print(f"loaded {added} tracks ({skipped} already present, kept)")
            print(f"corpus is now {len(store.corpus_ids())} tracks")
        else:
            count = export(args.out)
            size = args.out.stat().st_size / 1e6
            print(f"exported {count} tracks -> {args.out} ({size:.1f} MB)")
    except Exception as exc:  # noqa: BLE001 - the usual cause is a dead Redis
        sys.exit(f"{type(exc).__name__}: {exc}\n(is redis-server running?)")


if __name__ == "__main__":
    main()
