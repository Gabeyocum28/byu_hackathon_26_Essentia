"""push_tracks.py: analyze locally, stream RESP into the VM container's Redis."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "push_tracks.py"
spec = importlib.util.spec_from_file_location("push_tracks", SCRIPT)
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)

TRACK = {
    "track_id": "42",
    "title": "Blue in Green",
    "artist": "Miles Davis",
    "album": "Kind of Blue",
    "artwork_url": "http://x/a.jpg",
    "preview_url": "http://x/p.mp3",
}
FEATURES = {"embedding": [0.1, 0.2], "groove": [120.0, 0.9, 3.1, 0.5]}


def test_resp_encodes_command_as_bulk_strings():
    out = push.resp(["SET", "k", "v"])
    assert out == b"*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$1\r\nv\r\n"


def test_resp_measures_utf8_bytes_not_chars():
    out = push.resp(["SET", "k", "café"])
    assert b"$5\r\ncaf\xc3\xa9\r\n" in out


def test_payload_writes_store_key_layout():
    """Must mirror store.py exactly: track:{id}, features:{id}, corpus:ids."""
    blob = push.payload(TRACK, FEATURES)
    commands = blob.split(b"*3\r\n")
    assert b"track:42" in blob
    assert b"features:42" in blob
    assert b"SADD" in blob and b"corpus:ids" in blob
    # values are the same JSON store.py would write
    assert json.dumps(TRACK).encode() in blob
    assert json.dumps(FEATURES).encode() in blob
    assert len(commands) == 4  # leading split artifact + SET, SET, SADD
