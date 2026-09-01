"""Analyze tracks on this machine, push the vectors into the VM's Redis.

The ARM VM can't run essentia (no aarch64 wheels), so real feature vectors
for new tracks are computed here and streamed into the "hackathon"
container's Redis as RESP over `ssh ... docker exec redis-cli --pipe`.
Key layout mirrors server/store.py exactly.

Usage:
  python3 scripts/push_tracks.py 3135556 916424 ...
  python3 scripts/push_tracks.py --ids-from tracklist.txt   # one id per line

Config (env):
  ESSENCIA_SSH_HOST  default opc@163.192.48.114
  ESSENCIA_SSH_KEY   path to the private key (optional; ssh defaults apply)
  ESSENCIA_CONTAINER default hackathon
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

SSH_HOST = os.environ.get("ESSENCIA_SSH_HOST", "opc@163.192.48.114")
SSH_KEY = os.environ.get("ESSENCIA_SSH_KEY", "")
CONTAINER = os.environ.get("ESSENCIA_CONTAINER", "hackathon")


def resp(command: list[str]) -> bytes:
    """One Redis command in RESP wire format (what redis-cli --pipe reads)."""
    out = [f"*{len(command)}\r\n".encode()]
    for arg in command:
        raw = arg.encode()
        out.append(f"${len(raw)}\r\n".encode() + raw + b"\r\n")
    return b"".join(out)


def payload(track: dict, features: dict) -> bytes:
    """The three writes store.put_track would do, as RESP."""
    track_id = track["track_id"]
    return (
        resp(["SET", f"track:{track_id}", json.dumps(track)])
        + resp(["SET", f"features:{track_id}", json.dumps(features)])
        + resp(["SADD", "corpus:ids", track_id])
    )


def push(blob: bytes) -> None:
    ssh = ["ssh"] + (["-i", SSH_KEY] if SSH_KEY else []) + [SSH_HOST]
    cmd = ssh + ["sudo", "docker", "exec", "-i", CONTAINER, "redis-cli", "--pipe"]
    result = subprocess.run(cmd, input=blob, capture_output=True, timeout=60)
    if result.returncode != 0 or b"errors: 0" not in result.stdout:
        raise RuntimeError(result.stdout.decode() + result.stderr.decode())


def analyze(track: dict) -> dict:
    from music_recommendations.analysis import analyze_track

    mp3 = Path(tempfile.mkstemp(suffix=".mp3")[1])
    try:
        with urllib.request.urlopen(track["preview_url"], timeout=15) as r:
            mp3.write_bytes(r.read())
        features = analyze_track(mp3)
    finally:
        mp3.unlink(missing_ok=True)
    return {
        k: v.tolist() if hasattr(v, "tolist") else float(v)
        for k, v in features.items()
    }


def main() -> None:
    from music_recommendations.server import deezer

    args = sys.argv[1:]
    if args[:1] == ["--ids-from"]:
        ids = Path(args[1]).read_text().split()
    else:
        ids = args
    if not ids:
        sys.exit(__doc__)

    failures = []
    for n, track_id in enumerate(ids, 1):
        start = time.time()
        try:
            track = deezer.get_track(track_id)
            if track is None:
                raise RuntimeError("not on Deezer or no preview")
            push(payload(track, analyze(track)))
            print(f"[{n}/{len(ids)}] {track_id}: pushed "
                  f"{track['artist']} — {track['title'][:40]} "
                  f"({time.time()-start:.1f}s)")
        except Exception as exc:
            failures.append(track_id)
            print(f"[{n}/{len(ids)}] {track_id}: FAILED — {exc}")

    print(f"\ndone: {len(ids) - len(failures)} pushed, {len(failures)} failed")
    if failures:
        print("retry with: python3 scripts/push_tracks.py", *failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
