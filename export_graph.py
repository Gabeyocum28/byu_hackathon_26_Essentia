"""Export the analyzed library as graph JSON (nodes + all pairwise edges)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mvp.similarity import camelot, connection

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"

GENRE_GROUPS = {
    "Electronic": {"electronic", "electro", "electronica", "dance", "House", "techno"},
    "Rock & Indie": {"rock", "indie", "hard rock", "alternative", "heavy metal", "punk"},
    "Jazz & Instrumental": {"jazz", "instrumental", "classical", "ambient", "easy listening"},
    "Hip-Hop & R&B": {"Hip-Hop", "rnb", "rap"},
    "Pop": {"pop", "female vocalists", "male vocalists"},
    "Folk & Soul": {"folk", "country", "blues", "soul", "funk", "reggae"},
}


def genre_group(tags: list) -> str:
    for tag, _score in tags:
        for group, members in GENRE_GROUPS.items():
            if tag in members:
                return group
    return "Pop"


def main() -> None:
    library = json.loads((ROOT / "library.json").read_text())
    tracks = []
    for meta in library:
        feats = json.loads((CACHE / f"{meta['id']}.json").read_text())
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
                "group": genre_group(f["tags"]),
            }
        )

    edges = []
    for i, a in enumerate(tracks):
        for b in tracks[i + 1 :]:
            conn = connection(a["features"], b["features"])
            edges.append(
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
    edges.sort(key=lambda e: -e["score"])

    out = {"nodes": nodes, "edges": edges}
    (ROOT / "graph.json").write_text(json.dumps(out))
    scores = [e["score"] for e in edges]
    print(
        f"{len(nodes)} nodes, {len(edges)} edges | score min {min(scores):.2f} "
        f"median {sorted(scores)[len(scores)//2]:.2f} max {max(scores):.2f}"
    )
    print("groups:", {n['group'] for n in nodes})


if __name__ == "__main__":
    main()
