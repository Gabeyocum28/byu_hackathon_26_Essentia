# analysis/ — Person 4

Pure function: MP3 path in, dict of feature vectors out (spec §2.1).
Knows nothing about HTTP, Deezer, Redis, or the phone. No caching here —
Person 2 owns *when* analysis happens; you own *how*.

Rules:
- Only this lane may import essentia.
- One EffNet pass feeds every classification head. Never instantiate
  EffNet twice per track (genre is a head on the embedding, NOT
  PartitionedCall:0 on a second pass).
- Two MonoLoader decodes are correct: 16 kHz for EffNet, 44.1 kHz for
  rhythm DSP. Don't "optimize" that away.
- Head node names vary per head and bite silently. Every head lives in
  registry.py with verified input/output node names. Never assume the
  TensorflowPredict2D defaults.
- Output keys must match contract/features.py FEATURE_KEYS exactly.
- Groove extractor choices (swing, tempo folding) are open — yours to
  change freely; they live entirely inside groove.py.
