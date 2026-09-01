"""Add a classification head to a corpus that was analyzed without it.

The heads ride on the EffNet embedding, and the embedding is already in Redis.
So a new head does NOT need the audio back: it can be computed from what is
stored, for the whole corpus, in about a minute. That is the difference
between adding an axis and re-downloading tens of thousands of previews at
Deezer's rate limit.

  python3 scripts/backfill_heads.py            # every track missing "genre"
  python3 scripts/backfill_heads.py --head genre --batch 512

Only tracks that lack the key are touched, so this is resumable and safe to
run while a crawl is still writing new tracks. Run it again afterwards to
catch whatever landed in between.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from music_recommendations.analysis import registry  # noqa: E402
from music_recommendations.server import store  # noqa: E402


def _model(head_name: str):
    """Build one head from the registry, with its verified node names."""
    from essentia.standard import TensorflowPredict2D

    head = registry.HEADS[head_name]
    path = registry.MODELS_DIR / head.filename
    if not path.exists():
        sys.exit(f"{path} missing — run: python3 scripts/fetch_models.py")
    model = TensorflowPredict2D(
        graphFilename=str(path), input=head.input_node, output=head.output_node
    )
    classes = json.loads(
        (registry.MODELS_DIR / head.filename.replace(".pb", ".json")).read_text()
    )["classes"]
    return model, classes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head", default="genre", choices=sorted(registry.HEADS))
    parser.add_argument("--batch", type=int, default=512)
    args = parser.parse_args()

    ids = store.corpus_ids()
    print(f"corpus: {len(ids)} tracks; checking which lack {args.head!r}")
    model, classes = _model(args.head)
    print(f"head loaded: {len(classes)} classes")

    started = time.time()
    done = skipped = 0
    for start in range(0, len(ids), args.batch):
        chunk = ids[start:start + args.batch]
        blobs = store.get_many_features(chunk)

        pending, rows = [], []
        for track_id, features in zip(chunk, blobs):
            if not features or "embedding" not in features:
                continue
            if args.head in features:
                skipped += 1
                continue
            pending.append((track_id, features))
            rows.append(features["embedding"])
        if not pending:
            continue

        # One forward pass for the whole chunk: the per-call overhead dominates
        # this model, so batching is most of the speed.
        predictions = model(np.array(rows, dtype=np.float32))
        for (track_id, features), vector in zip(pending, predictions):
            track = store.get_track(track_id)
            if track is None:
                continue
            store.put_track(track, {**features, args.head: vector.tolist()})
            done += 1

        elapsed = time.time() - started
        print(f"  {start + len(chunk)}/{len(ids)}  written {done}  "
              f"already had it {skipped}  ({elapsed:.0f}s)", flush=True)

    print(f"\nbackfilled {args.head} onto {done} tracks in "
          f"{time.time() - started:.0f}s ({skipped} already had it)")


if __name__ == "__main__":
    main()
