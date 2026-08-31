# Music Connections MVP

Audio-based, explainable music recommendations from free data:
Deezer's public API (30s previews + metadata, no auth) analyzed with
[Essentia](https://essentia.upf.edu/) + its MusiCNN TensorFlow model.

## Why this beats collaborative filtering

Spotify/Apple Music recommend from listening co-occurrence. That fails on
new/obscure tracks (cold start) and can't say *why* two songs connect.
We analyze the actual audio, so every recommendation ships with reasons:
timbre match %, tempo compatibility (half/double-time aware), and harmonic
key compatibility on the Camelot wheel — the same rules DJs mix by.

## Data extracted per track

- From Deezer: title, artist, album, duration, popularity rank, ISRC, preview MP3
- From Essentia: BPM, musical key + confidence, danceability, loudness,
  50 genre/mood/instrument tags, 200-dim neural timbre embedding

## Run it

```
pip install essentia-tensorflow
python3 run_mvp.py        # builds a 20-track library, prints recommendations
python3 -m pytest         # 26 unit tests
```

Analysis is cached in `cache/` (JSON per track), previews in `samples/`.

## Layout

- `mvp/deezer.py` — Deezer API client (search, charts, related artists, previews)
- `mvp/analyzer.py` — Essentia feature + embedding extraction, cached
- `mvp/similarity.py` — pure scoring math (Camelot key wheel, tempo, cosine)
- `mvp/recommend.py` — ranking + human-readable explanations
- `run_mvp.py` — end-to-end demo
- `essentia_demo.py` — original minimal demo
