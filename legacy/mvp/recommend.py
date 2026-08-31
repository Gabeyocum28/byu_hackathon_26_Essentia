"""Build a track library and produce explainable recommendations."""

from __future__ import annotations

from mvp.similarity import connection


def recommend(seed: dict, library: list[dict], top_n: int = 5) -> list[dict]:
    """Rank library tracks by audio connection to the seed track.

    Each result carries the connection score, per-component breakdown, and
    human-readable reasons — the explainability Spotify/Apple Music don't give.
    """
    results = []
    for other in library:
        if other["id"] == seed["id"]:
            continue
        conn = connection(seed["features"], other["features"])
        results.append({**other, "connection": conn})
    results.sort(key=lambda r: -r["connection"]["score"])
    return results[:top_n]


def format_recommendation(rank: int, rec: dict) -> str:
    conn = rec["connection"]
    c = conn["components"]
    lines = [
        f"  {rank}. {rec['artist']} - {rec['title']}"
        f"   [score {conn['score']:.2f}]",
        f"     components: sound {c['embedding']:.2f} | "
        f"tempo {c['bpm']:.2f} | key {c['key']:.2f}",
    ]
    for reason in conn["reasons"]:
        lines.append(f"     - {reason}")
    return "\n".join(lines)
