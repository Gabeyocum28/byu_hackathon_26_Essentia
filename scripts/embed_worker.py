"""Pop embed jobs off the VM's Redis, run Essentia locally, write back.

The ARM VM can't import essentia, so /seed queues cold tracks instead of
analyzing them; this worker is the other half. Run it on a machine where
essentia imports (the Mac), pointed at the VM's Redis:

    REDIS_URL=redis://<vm-ip>:6379/0 python3 scripts/embed_worker.py

One process, one job at a time: on-demand taps trickle in and analysis is
~1 s. Bulk backfill stays push_tracks.py's job.
"""
from __future__ import annotations

import os
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

from music_recommendations.analysis import analyze_track
from music_recommendations.server import deezer, store, viz


def download_preview(url: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    path = Path(name)
    with urllib.request.urlopen(url, timeout=10) as resp:
        path.write_bytes(resp.read())
    return path


def _to_plain(features: dict) -> dict:
    return {
        k: v.tolist() if hasattr(v, "tolist") else v for k, v in features.items()
    }


def _fresh_track(track_id: str) -> dict | None:
    """Prefer a fresh Deezer fetch over the stored record: preview URLs
    expire in ~15 min (hdnea token), so a job that waited in the queue
    would 403 on download if we trusted the URL /seed stored."""
    try:
        track = deezer.get_track(track_id)
    except Exception:
        track = None
    return track or store.get_track(track_id)


def process_job(track_id: str) -> bool:
    """Analyze one queued track. True on success; logs and swallows failures
    so one bad track never kills the loop."""
    try:
        track = _fresh_track(track_id)
        if track is None:
            print(f"[embed_worker] {track_id}: no metadata in Redis or on Deezer", flush=True)
            return False
        mp3 = download_preview(track["preview_url"])
        try:
            features = _to_plain(analyze_track(mp3))
        finally:
            mp3.unlink(missing_ok=True)
        store.put_track(track, features)
        print(f"[embed_worker] {track_id}: analyzed  {track['artist']} - {track['title']}", flush=True)
        return True
    except Exception as exc:
        print(f"[embed_worker] {track_id}: FAILED  {exc}", flush=True)
        return False
    finally:
        # Always drop the dedup guard: a failed job should be re-enqueueable
        # by the next tap, not stuck behind a stale marker.
        try:
            store.clear_embed_marker(track_id)
        except Exception:
            pass


def _write_wav(samples: "np.ndarray", sample_rate: int) -> Path:
    """16-bit PCM temp file: MonoLoader wants a path, not an array."""
    import numpy as np

    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    path = Path(name)
    peak = float(np.max(np.abs(samples))) or 1.0
    pcm = np.clip(samples / peak * 0.98, -1.0, 1.0)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes((pcm * 32767).astype("<i2").tobytes())
    return path


def _cosine(a: "np.ndarray", b: "np.ndarray") -> float:
    import numpy as np

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def process_attribution(seed_id: str, rec_id: str) -> bool:
    """Occlusion attribution for one (seed, rec) pair.

    For each band: delete it from the SEED's waveform, push the
    counterfactual through the real frozen model, and measure how far the
    pair's cosine falls. The drops are not additive (bands interact inside
    the network) -- this is the tractable first-order surrogate for Shapley
    values, and what the audience hears removed is exactly what the model
    lost.
    """
    import numpy as np

    from music_recommendations.analysis import embedding as embed_mod

    mp3 = None
    try:
        seed_features = store.get_features(seed_id)
        rec_features = store.get_features(rec_id)
        if not seed_features or not rec_features:
            raise ValueError("both tracks must be analyzed")
        seed_vec = np.asarray(seed_features["embedding"], dtype=float)
        rec_vec = np.asarray(rec_features["embedding"], dtype=float)
        # The baseline compares the STORED embeddings: re-embedding the clean
        # seed here would measure decode jitter as if it were attribution.
        base = _cosine(seed_vec, rec_vec)

        track = _fresh_track(seed_id)
        if track is None:
            raise ValueError("no seed metadata in Redis or on Deezer")
        mp3 = download_preview(track["preview_url"])
        audio = embed_mod.load_audio(mp3)          # mono, 16 kHz — model rate

        bands = []
        for lo_hz, hi_hz in viz.band_edges():
            started = time.monotonic()
            filtered = viz.band_stop(audio, embed_mod.SAMPLE_RATE, lo_hz, hi_hz)
            wav = _write_wav(filtered, embed_mod.SAMPLE_RATE)
            try:
                occluded = embed_mod.effnet_frames(wav).mean(axis=0)
            finally:
                wav.unlink(missing_ok=True)
            delta = base - _cosine(occluded, rec_vec)
            bands.append({"lo_hz": round(lo_hz, 1), "hi_hz": round(hi_hz, 1),
                          "delta": float(delta)})
            print(f"[embed_worker] attr {seed_id}->{rec_id} "
                  f"{lo_hz:.0f}-{hi_hz:.0f}Hz delta={delta:+.4f} "
                  f"({time.monotonic() - started:.1f}s)", flush=True)

        store.put_attribution(seed_id, rec_id, {
            "status": "ready", "base": base, "bands": bands,
        })
        print(f"[embed_worker] attr {seed_id}->{rec_id}: ready "
              f"(base {base:.3f})", flush=True)
        return True
    except Exception as exc:
        print(f"[embed_worker] attr {seed_id}->{rec_id}: FAILED  {exc}", flush=True)
        try:
            # Cache the failure briefly so the phone stops polling, but let
            # the pair be retried once the TTL lapses.
            store.put_attribution(seed_id, rec_id,
                                  {"status": "failed", "error": str(exc)}, ttl=60)
        except Exception:
            pass
        return False
    finally:
        if mp3 is not None:
            mp3.unlink(missing_ok=True)
        try:
            store.clear_attribution_marker(seed_id, rec_id)
        except Exception:
            pass


def _tick() -> None:
    """One loop iteration: dequeue and process a job, if there is one.

    The process_* helpers never raise, but store.dequeue_job can (a transient
    Redis ConnectionError on the blocking pop) -- guard it here so main()'s
    loop survives a Redis blip instead of dying.
    """
    try:
        job = store.dequeue_job(timeout=5)
        if not job:
            return
        kind, payload = job
        if kind == "embed":
            process_job(payload)
        else:
            seed_id, _, rec_id = payload.partition("|")
            if seed_id and rec_id:
                process_attribution(seed_id, rec_id)
            else:
                print(f"[embed_worker] bad attribution job {payload!r}", flush=True)
    except Exception as exc:
        print(f"[embed_worker] queue error {exc}, retrying in 5s", flush=True)
        time.sleep(5)


def main() -> None:
    print("[embed_worker] watching embed:queue + attr:queue (Ctrl-C to stop)",
          flush=True)
    while True:
        _tick()


if __name__ == "__main__":
    main()
