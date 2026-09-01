"""deezer.py: Deezer search JSON -> contract Track dicts."""
from music_recommendations.server import deezer

DEEZER_RESPONSE = {
    "data": [
        {
            "id": 3135556,
            "title": "So What",
            "artist": {"name": "Miles Davis"},
            "album": {"title": "Kind of Blue", "cover_medium": "http://x/a.jpg"},
            "preview": "http://x/p.mp3",
        },
        {
            "id": 999,
            "title": "No Preview Here",
            "artist": {"name": "Nobody"},
            "album": {"title": "Silence", "cover_medium": "http://x/b.jpg"},
            "preview": "",
        },
    ]
}


def test_search_maps_to_contract_track_shape(monkeypatch):
    monkeypatch.setattr(deezer, "_get_json", lambda url: DEEZER_RESPONSE)
    results = deezer.search("so what")
    assert results[0] == {
        "track_id": "3135556",
        "title": "So What",
        "artist": "Miles Davis",
        "album": "Kind of Blue",
        "artwork_url": "http://x/a.jpg",
        "preview_url": "http://x/p.mp3",
    }


def test_search_drops_tracks_without_preview(monkeypatch):
    monkeypatch.setattr(deezer, "_get_json", lambda url: DEEZER_RESPONSE)
    results = deezer.search("so what")
    assert [t["track_id"] for t in results] == ["3135556"]


def test_search_urlencodes_query(monkeypatch):
    seen = {}

    def fake(url):
        seen["url"] = url
        return {"data": []}

    monkeypatch.setattr(deezer, "_get_json", fake)
    deezer.search("miles davis & co")
    assert "miles+davis+%26+co" in seen["url"]


def test_get_track_returns_contract_shape(monkeypatch):
    monkeypatch.setattr(deezer, "_get_json", lambda url: DEEZER_RESPONSE["data"][0])
    track = deezer.get_track("3135556")
    assert track["track_id"] == "3135556"
    assert track["preview_url"] == "http://x/p.mp3"
