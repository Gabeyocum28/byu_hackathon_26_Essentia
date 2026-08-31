from music_recommendations.corpus import crawl


def test_snowball_dedupes_artists_and_tracks(monkeypatch):
    artists = {1: [{"id": 2, "name": "B"}], 2: [{"id": 1, "name": "A"}]}
    track = {
        "track_id": "9", "title": "T", "artist": "A", "album": "",
        "artwork_url": "", "preview_url": "https://p",
    }
    monkeypatch.setattr(crawl.deezer, "search_artist", lambda n: {"id": 1, "name": "A"})
    monkeypatch.setattr(crawl.deezer, "related_artists", lambda i, limit: artists.get(i, []))
    monkeypatch.setattr(crawl.deezer, "artist_top_tracks", lambda i, limit: [track])
    out = crawl.snowball(["A"], hops=2)
    assert out == [track]   # same track from both artists -> one entry
