"""Analyze tracks on this machine, push the vectors into the VM's Redis.

The ARM VM can't run essentia (no aarch64 wheels), so real feature vectors
for new tracks are computed here and streamed into the "hackathon"
container's Redis as RESP over `ssh ... docker exec redis-cli --pipe`.
Key layout mirrors server/store.py exactly.

Usage:
  python3 scripts/push_tracks.py 3135556 916424 ...
  python3 scripts/push_tracks.py --ids-from tracklist.txt   # one id per line
  python3 scripts/push_tracks.py --charts                   # every Deezer genre chart
  python3 scripts/push_tracks.py --charts --workers 6       # default: 75% of cores

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


def default_workers(cores: int | None = None) -> int:
    cores = cores or os.cpu_count() or 1
    return max(1, int(cores * 0.75))


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)


def chart_tracks(skip_ids: set[str]) -> list[dict]:
    """Contract-shaped tracks from every Deezer genre chart, deduped."""
    from music_recommendations.server.deezer import API, _to_track

    genres = _get_json(f"{API}/genre")["data"]
    seen: dict[str, dict] = {}
    for g in genres:
        try:
            items = _get_json(f"{API}/chart/{g['id']}/tracks?limit=100")["data"]
        except Exception:
            continue  # some genres have no chart; skip, don't die
        for item in items:
            tid = str(item["id"])
            if item.get("preview") and tid not in skip_ids and tid not in seen:
                seen[tid] = _to_track(item)
    return list(seen.values())


def corpus_ids_on_vm() -> set[str]:
    ssh = ["ssh"] + (["-i", SSH_KEY] if SSH_KEY else []) + [SSH_HOST]
    cmd = ssh + ["sudo", "docker", "exec", CONTAINER,
                 "redis-cli", "smembers", "corpus:ids"]
    out = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
    return set(out.stdout.split()) if out.returncode == 0 else set()


def _process_track(track: dict) -> tuple[str, str]:
    """Worker: analyze one track and push it. Returns (track_id, error or '')."""
    try:
        push(payload(track, analyze(track)))
        return track["track_id"], ""
    except Exception as exc:
        return track["track_id"], str(exc)[:200]


def run_parallel(tracks: list[dict], workers: int) -> list[str]:
    """Analyze+push tracks across worker processes; returns failed ids."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, as_completed

    failures = []
    start = time.time()
    # spawn, not fork: forking after TensorFlow has loaded wedges on macOS
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=mp.get_context("spawn")
    ) as pool:
        futures = {pool.submit(_process_track, t): t for t in tracks}
        for n, fut in enumerate(as_completed(futures), 1):
            tid, err = fut.result()
            t = futures[fut]
            rate = n / (time.time() - start) * 60
            if err:
                failures.append(tid)
                print(f"[{n}/{len(tracks)}] {tid}: FAILED — {err}")
            else:
                print(f"[{n}/{len(tracks)}] {tid}: {t['artist']} — "
                      f"{t['title'][:35]} ({rate:.0f}/min)")
    return failures


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
    workers = 0
    if "--workers" in args:
        i = args.index("--workers")
        workers = int(args[i + 1])
        del args[i:i + 2]

    if args[:1] == ["--charts"]:
        existing = corpus_ids_on_vm()
        tracks = chart_tracks(skip_ids=existing)
        workers = workers or default_workers()
        print(f"{len(tracks)} chart tracks to push "
              f"({len(existing)} already in corpus); {workers} workers")
        failures = run_parallel(tracks, workers)
        print(f"\ndone: {len(tracks) - len(failures)} pushed, {len(failures)} failed")
        if failures:
            print("retry with: python3 scripts/push_tracks.py", *failures)
            sys.exit(1)
        return

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
