"""Freeze the analyzed corpus into files the server can read without Redis.

Redis does not leave the machine it runs on, and no free managed tier comes
close to holding this corpus: 90k tracks occupy ~3.6 GB there because every
vector is stored as JSON *text* -- one 1280-float embedding is ~28 KB of
ASCII. The same numbers as float16 are 2.5 KB, so the whole corpus fits in
roughly 440 MB and can simply be uploaded alongside the code.

  python3 scripts/export_snapshot.py [--out corpus_snapshot] [--dtype float16]

Writes, into the output directory:

  ids.json        track ids, one per matrix row, in row order
  tracks.json     contract Track fields per id, aligned to ids.json
  embedding.npy   (n_tracks, 1280)

Only `embedding` travels. Both live axes rank on it -- sounds_like takes the
nearest by cosine, surprise the most distant -- so it is the whole product.
The corpus also holds `genre` (58,842 tracks) and `groove` (the older 31,649),
but no axis reads either any more, and exporting a key only some tracks have
would drop a third of the corpus from the matrix to no purpose.

preview_url is deliberately NOT exported. It is a ~15-minute Deezer
signature: baking 90k of them into a snapshot would ship 90k values that are
wrong before the upload finishes. The server re-signs on demand instead --
see GET /preview.

float32 is the default, measured rather than assumed. Against the original
float64 vectors over 200 random seeds:

  float16  221 MB   top-10 set 99.6% identical, exact order on 162/200 seeds
  float32  442 MB   top-10 set  100% identical, exact order on 198/200 seeds

float16 is defensible -- it never moved more than one track in a top ten --
but 221 MB of extra upload is cheap next to explaining why the hosted server
orders results differently from the laptop. Pass --dtype float16 to halve it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))   # contract/ lives at the repo root

from contract.features import FEATURE_KEYS, TRACK_FIELDS  # noqa: E402
from music_recommendations.server import store  # noqa: E402

KEY = "embedding"

# One mget of the whole corpus would pull every vector into memory at once --
# the 3.6 GB this script exists to avoid. Batches keep the peak flat.
BATCH = 1000


def _batches(items: list[str], size: int = BATCH):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def export(out_dir: Path, dtype: str) -> None:
    ids_all = store.corpus_ids()
    print(f"corpus: {len(ids_all)} analyzed tracks")
    if not ids_all:
        raise SystemExit("nothing to export -- corpus:ids is empty")

    kept: list[str] = []
    rows: list[np.ndarray] = []
    skipped = 0

    for batch in _batches(ids_all):
        for track_id, features in zip(batch, store.get_many_features(batch)):
            if not features or KEY not in features:
                skipped += 1
                continue
            kept.append(track_id)
            rows.append(np.asarray(features[KEY], dtype=dtype))
        print(f"  read {len(kept) + skipped}/{len(ids_all)}", end="\r", flush=True)
    print()
    if skipped:
        print(f"skipped {skipped} tracks with no {KEY}")

    matrix = np.stack(rows)
    expected = FEATURE_KEYS[KEY]
    if matrix.shape[1] != expected:
        raise SystemExit(f"{KEY}: width {matrix.shape[1]}, contract says {expected}")

    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / f"{KEY}.npy", matrix)
    (out_dir / "ids.json").write_text(json.dumps(kept))

    # Metadata rides as one file rather than 90k keys: the server reads it
    # whole at startup, and 90k separate reads is what made Redis slow here.
    meta = []
    for batch in _batches(kept):
        for track_id, track in zip(batch, store.get_many_tracks(batch)):
            track = track or {"track_id": track_id}
            meta.append({k: v for k, v in track.items()
                         if k in TRACK_FIELDS and k != "preview_url"})
    (out_dir / "tracks.json").write_text(json.dumps(meta))

    for path in sorted(out_dir.iterdir()):
        print(f"  {path.name:16} {path.stat().st_size / 2**20:8.1f} MB")
    total = sum(p.stat().st_size for p in out_dir.iterdir()) / 2**20
    print(f"\nwrote {len(kept)} tracks to {out_dir}/  ({total:.0f} MB total)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("corpus_snapshot"))
    parser.add_argument("--dtype", default="float32", choices=["float16", "float32"])
    args = parser.parse_args()
    export(args.out, args.dtype)


if __name__ == "__main__":
    main()
