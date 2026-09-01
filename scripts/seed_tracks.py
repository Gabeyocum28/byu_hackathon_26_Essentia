"""Seed tracks into a running server, one blocking POST /seed at a time.

Usage:
  python3 scripts/seed_tracks.py                     # all of contract/fixture.json
  python3 scripts/seed_tracks.py 3135556 916424      # specific track ids
  SERVER_URL=http://vm:8000 python3 scripts/seed_tracks.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

SERVER = os.environ.get("SERVER_URL", "http://localhost:8000")


def seed(track_id: str) -> str:
    req = urllib.request.Request(
        f"{SERVER}/seed",
        data=json.dumps({"track_id": track_id}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["status"]


def main() -> None:
    ids = sys.argv[1:]
    if not ids:
        fixture = Path(__file__).parents[1] / "contract" / "fixture.json"
        ids = [t["track_id"] for t in json.loads(fixture.read_text())["tracks"]]

    failures = []
    for n, track_id in enumerate(ids, 1):
        start = time.time()
        try:
            status = seed(track_id)
            print(f"[{n}/{len(ids)}] {track_id}: {status} ({time.time()-start:.1f}s)")
        except Exception as exc:
            failures.append(track_id)
            print(f"[{n}/{len(ids)}] {track_id}: FAILED — {exc}")

    print(f"\ndone: {len(ids) - len(failures)} ok, {len(failures)} failed")
    if failures:
        print("retry with:", "python3 scripts/seed_tracks.py", *failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
