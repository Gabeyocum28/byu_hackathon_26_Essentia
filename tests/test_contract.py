import importlib.util
import json
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[1] / "contract"


def _features():
    spec = importlib.util.spec_from_file_location("features", CONTRACT / "features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_axes_ids_match_spec():
    f = _features()
    # best_match was added after the spec's original three: it blends the
    # embedding and groove percentiles rather than ranking on one key.
    assert [a["id"] for a in f.AXES] == [
        "sounds_like", "groove", "surprise", "best_match",
    ]


def test_track_fields():
    f = _features()
    assert f.TRACK_FIELDS == {
        "track_id", "title", "artist", "album", "artwork_url", "preview_url"
    }


def test_fixture_thirty_contract_tracks():
    f = _features()
    data = json.loads((CONTRACT / "fixture.json").read_text())
    assert len(data["tracks"]) == 30
    for t in data["tracks"]:
        assert set(t) == f.TRACK_FIELDS
        assert t["preview_url"].startswith("http")
        assert isinstance(t["track_id"], str)
