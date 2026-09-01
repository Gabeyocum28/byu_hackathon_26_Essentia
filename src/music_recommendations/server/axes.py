"""Axis registry: axis id -> (feature key in the analysis dict, direction).

THE one table for adding, removing, or reweighting an axis (spec §2.2).
Labels served by GET /axes come from contract/features.py — the client
renders whatever this sends.
"""
from __future__ import annotations

from contract.features import AXES

AXIS_FEATURES: dict[str, tuple[str, int]] = {
    "sounds_like": ("embedding", 1),
    "groove":      ("groove", 1),
    "surprise":    ("embedding", -1),   # most distant by embedding cosine
}

# This table and contract AXES must list the same ids: /axes serves the
# contract list while /recommend validates against this one, so if they drift
# the client renders a button that 400s. Fail at import, not at request time.
_contract_ids = {a["id"] for a in AXES}
assert set(AXIS_FEATURES) == _contract_ids, (
    f"axes.py {sorted(AXIS_FEATURES)} != contract AXES {sorted(_contract_ids)}"
)
