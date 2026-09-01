"""Snowball crawl: 8 roots -> 2 hops of /related -> top tracks, deduped.

Two ways to build a candidate pool, because the project widened from jazz to
all music partway through:

  snowball()   the artist-relatedness graph. Dense and coherent -- everything
               two hops from Miles Davis is jazz -- but it only ever explores
               one neighbourhood of the catalogue.
  from_charts() Deezer's per-genre charts. Broad and shallow, and the only
               cheap way to get a pool that spans rock, classical, hip-hop and
               the rest at once.

Use from_charts for breadth, snowball to deepen around a genre you care about,
or both: they both emit contract Track dicts deduped by track_id.
"""
from __future__ import annotations

from music_recommendations.corpus import deezer

ROOTS = [
    "Miles Davis", "Duke Ellington", "Django Reinhardt", "Ornette Coleman",
    "Bill Evans", "Stan Getz", "Jimmy Smith", "Weather Report",
]

# Deezer genre ids. Not exhaustive -- a spread wide enough that the embedding
# has genuinely different things to tell apart.
GENRES = {
    132: "pop", 116: "rap/hiphop", 152: "rock", 113: "dance", 165: "r&b",
    85: "alternative", 106: "electro", 466: "folk", 144: "reggae",
    129: "jazz", 98: "classical", 84: "country", 464: "metal",
    169: "soul/funk", 153: "blues", 75: "latin", 2: "african",
}


def snowball_artists(root_names: list[str], hops: int = 2, per_artist: int = 20) -> list[dict]:
    """BFS out from root_names over /related, deduped by artist id."""
    seen: dict[int, dict] = {}
    frontier = []
    for name in root_names:
        artist = deezer.search_artist(name)
        if artist and artist["id"] not in seen:
            seen[artist["id"]] = artist
            frontier.append(artist)

    for _hop in range(hops):
        next_frontier = []
        for artist in frontier:
            for related in deezer.related_artists(artist["id"], limit=per_artist):
                if related["id"] not in seen:
                    seen[related["id"]] = related
                    next_frontier.append(related)
        frontier = next_frontier
        if not frontier:
            break
    return list(seen.values())


def snowball(root_names: list[str] = ROOTS, hops: int = 2, per_artist: int = 20) -> list[dict]:
    """All candidate tracks (contract shape, preview required), deduped by id."""
    tracks: dict[str, dict] = {}
    for artist in snowball_artists(root_names, hops=hops, per_artist=per_artist):
        for track in deezer.artist_top_tracks(artist["id"], limit=per_artist):
            tracks.setdefault(track["track_id"], track)
    return list(tracks.values())


def from_charts(genre_ids: list[int] | None = None, per_genre: int = 100) -> list[dict]:
    """Even slice of each genre chart, deduped by track_id."""
    tracks: dict[str, dict] = {}
    for genre_id in genre_ids or list(GENRES):
        for track in deezer.chart_tracks(genre_id, limit=per_genre):
            tracks.setdefault(track["track_id"], track)
    return list(tracks.values())
