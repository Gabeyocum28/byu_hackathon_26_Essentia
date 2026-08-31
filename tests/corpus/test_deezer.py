from music_recommendations.corpus import deezer

RAW = {
    "id": 3135556, "title": "So What",
    "artist": {"id": 1910, "name": "Miles Davis"},
    "album": {"title": "Kind of Blue", "cover_medium": "https://img/x.jpg"},
    "preview": "https://cdn/preview.mp3",
}


def test_track_to_contract_shape():
    t = deezer.track_to_contract(RAW)
    assert t == {
        "track_id": "3135556",
        "title": "So What",
        "artist": "Miles Davis",
        "album": "Kind of Blue",
        "artwork_url": "https://img/x.jpg",
        "preview_url": "https://cdn/preview.mp3",
    }


def test_track_without_preview_is_dropped():
    assert deezer.track_to_contract({**RAW, "preview": ""}) is None
