"""Export the analyzed library as graph JSON and render sound_connections.html."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mvp.analyzer import CACHE_VERSION
from mvp.similarity import camelot, connection

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"

# Discogs parent category -> the graph's six legend groups.
FAMILY_GROUPS = {
    "Electronic": "Electronic",
    "Rock": "Rock & Indie",
    "Jazz": "Jazz & Instrumental",
    "Classical": "Jazz & Instrumental",
    "Stage & Screen": "Jazz & Instrumental",
    "Non-Music": "Jazz & Instrumental",
    "Hip Hop": "Hip-Hop & R&B",
    "Pop": "Pop",
    "Funk / Soul": "Folk & Soul",
    "Reggae": "Folk & Soul",
    "Folk, World, & Country": "Folk & Soul",
    "Blues": "Folk & Soul",
    "Latin": "Folk & Soul",
}


def genre_group(families: list) -> str:
    for family, _score in families:
        if family in FAMILY_GROUPS:
            return FAMILY_GROUPS[family]
    return "Pop"


def main() -> None:
    library = json.loads((ROOT / "library.json").read_text())
    tracks = []
    for meta in library:
        feats = json.loads((CACHE / f"{meta['id']}.json").read_text())
        if feats.get("version") != CACHE_VERSION:
            raise SystemExit(
                f"stale cache for track {meta['id']} — run run_mvp.py first"
            )
        feats["embedding"] = np.array(feats["embedding"])
        feats["tags"] = [tuple(t) for t in feats["tags"]]
        tracks.append({**meta, "features": feats})

    nodes = []
    for t in tracks:
        f = t["features"]
        num, letter = camelot(f["key"], f["scale"])
        nodes.append(
            {
                "id": t["id"],
                "title": t["title"],
                "artist": t["artist"],
                "album": t["album"],
                "link": t["link"],
                "rank": t["rank"],
                "bpm": round(f["bpm"], 1),
                "key": f["key"],
                "scale": f["scale"],
                "camelot": f"{num}{letter}",
                "danceability": round(f["danceability"], 2),
                "tags": [t2 for t2, _ in f["tags"][:4]],
                "group": genre_group(f["genre_families"]),
                "mood": f["mood"],
                "valence": f["valence"],
                "arousal": f["arousal"],
            }
        )

    all_edges = []
    for i, a in enumerate(tracks):
        for b in tracks[i + 1 :]:
            conn = connection(a["features"], b["features"])
            all_edges.append(
                {
                    "source": a["id"],
                    "target": b["id"],
                    "score": round(conn["score"], 3),
                    "sound": round(conn["components"]["embedding"], 2),
                    "tempo": round(conn["components"]["bpm"], 2),
                    "key": round(conn["components"]["key"], 2),
                    "reasons": conn["reasons"],
                }
            )

    # On big libraries the complete graph is unreadable (and megabytes of
    # JSON): keep each node's TOP_K strongest connections, union'd.
    TOP_K = 6
    if len(tracks) > 40:
        per_node: dict[int, list] = {}
        for e in all_edges:
            per_node.setdefault(e["source"], []).append(e)
            per_node.setdefault(e["target"], []).append(e)
        keep = set()
        for conns in per_node.values():
            conns.sort(key=lambda e: -e["score"])
            for e in conns[:TOP_K]:
                keep.add(id(e))
        edges = [e for e in all_edges if id(e) in keep]
    else:
        edges = all_edges
    edges.sort(key=lambda e: -e["score"])

    out = {"nodes": nodes, "edges": edges}
    (ROOT / "graph.json").write_text(json.dumps(out))

    template = (ROOT / "graph_template.html").read_text()
    page = template.replace("__GRAPH_DATA__", json.dumps(out))
    (ROOT / "sound_connections.html").write_text(page)

    scores = [e["score"] for e in edges]
    print(
        f"{len(nodes)} nodes, {len(edges)} edges | score min {min(scores):.2f} "
        f"median {sorted(scores)[len(scores)//2]:.2f} max {max(scores):.2f}"
    )
    print("groups:", {n["group"] for n in nodes})
    print("rendered sound_connections.html")


if __name__ == "__main__":
    main()
