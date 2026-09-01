# HTTP contract — frozen

```
GET /search?q=miles+davis+so+what
→ { "results": [ Track, ... ] }

POST /seed  { "track_id": "3135556" }
→ { "track_id": "3135556", "status": "ready" }
   Blocks until analysis completes. Cold ~1-2s (0.8s analysis plus
   preview download), warm instant.

GET /axes
→ { "axes": [ { "id": "sounds_like", "label": "Sounds like this" },
              { "id": "mood",        "label": "Keep the feeling"  },
              { "id": "groove",      "label": "Keep the groove"   },
              { "id": "surprise",    "label": "Surprise me"       } ] }

GET /recommend?track_id=3135556&axis=groove&limit=10
→ { "seed_track_id": "3135556", "axis": "groove", "results": [ Track, ... ] }
```

Every `Track` object is the same shape at every endpoint:

```json
{
  "track_id": "3135556",
  "title": "So What",
  "artist": "Miles Davis",
  "album": "Kind of Blue",
  "artwork_url": "https://...",
  "preview_url": "https://...",
  "score": 0.91
}
```

`score` is present on recommendation results only, and exists for debugging. The v1 UI ignores it.

### Three deliberate choices

**`/axes` is an endpoint, not hardcoded in Swift.** The axis list is not settled and may shrink. The client renders whatever buttons the server sends, so changing the axis list never requires touching iOS.

**`POST /seed` is synchronous.** An async status/polling design costs the server a state machine and the client another one. A five-second blocking HTTP request is fine and removes real work from both sides of the biggest seam.

**Uniform `Track` shape.** One Swift struct, decoded identically everywhere.
