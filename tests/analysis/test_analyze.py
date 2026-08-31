import numpy as np
import pytest

from music_recommendations.analysis import registry


def test_analyze_track_matches_feature_keys(tmp_path):
    pytest.importorskip("essentia")
    if not (registry.MODELS_DIR / registry.EFFNET_FILE).exists():
        pytest.skip("models/ not fetched; run scripts/fetch_models.py")

    import json
    from pathlib import Path

    from music_recommendations.analysis import analyze_track
    from music_recommendations.corpus.download import download_preview

    contract = Path(__file__).resolve().parents[2] / "contract"
    keys = json.loads((contract / "fixture.json").read_text())
    mp3 = download_preview(keys["tracks"][0], tmp_path)

    feats = analyze_track(mp3)
    assert feats["embedding"].shape == (1280,)
    assert feats["genre"].shape == (400,)
    assert feats["moodtheme"].shape == (56,)
    assert 0.0 <= feats["mood_happy"] <= 1.0
    assert feats["groove"].shape == (4,)
    assert np.isfinite(feats["groove"]).all()
