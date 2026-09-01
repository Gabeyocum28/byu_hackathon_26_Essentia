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


def _item(track_id, title, rank, artist="X"):
    return {
        "id": track_id,
        "title": title,
        "rank": rank,
        "artist": {"name": artist},
        "album": {"title": "A", "cover_medium": "http://x/a.jpg"},
        "preview": "http://x/p.mp3",
    }


def test_search_runs_plain_and_exact_title_queries(monkeypatch):
    """Deezer's fuzzy search misses punctuated titles the track:"..." field
    search finds — both must be queried."""
    urls = []

    def fake(url):
        urls.append(url)
        return {"data": []}

    monkeypatch.setattr(deezer, "_get_json", fake)
    deezer.search("sing about me, i'm dying of thirst")
    assert len(urls) == 2
    assert "track%3A%22" in urls[1]          # track:"..." field query


def test_search_orders_by_popularity_and_dedupes(monkeypatch):
    responses = iter([
        {"data": [_item(1, "Cover (Lofi)", 42_000), _item(2, "Cover", 26_000)]},
        {"data": [_item(3, "Original", 324_000, artist="Kendrick Lamar"),
                  _item(1, "Cover (Lofi)", 42_000)]},
    ])
    monkeypatch.setattr(deezer, "_get_json", lambda url: next(responses))
    results = deezer.search("whatever")
    assert [t["track_id"] for t in results] == ["3", "1", "2"]


def test_search_tolerates_exact_query_failure(monkeypatch):
    calls = {"n": 0}

    def fake(url):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("deezer hiccup")
        return {"data": [_item(1, "Song", 10)]}

    monkeypatch.setattr(deezer, "_get_json", fake)
    assert [t["track_id"] for t in deezer.search("song")] == ["1"]


def test_search_raises_when_deezer_down(monkeypatch):
    """/search's fixture fallback depends on the exception propagating."""
    def boom(url):
        raise OSError("no network")

    monkeypatch.setattr(deezer, "_get_json", boom)
    import pytest
    with pytest.raises(OSError):
        deezer.search("anything")


def test_get_track_returns_contract_shape(monkeypatch):
    monkeypatch.setattr(deezer, "_get_json", lambda url: DEEZER_RESPONSE["data"][0])
    track = deezer.get_track("3135556")
    assert track["track_id"] == "3135556"
    assert track["preview_url"] == "http://x/p.mp3"
