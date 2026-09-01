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

# Axes that blend several feature keys instead of ranking on one.
#
# Ranking on a single key picks extremists: for a Miles Davis seed, pure
# embedding returned a track sitting at the 21st percentile of groove, and pure
# groove returned one at the 19th percentile of sound. Each is the right answer
# to a narrower question than "what is similar to this". Requiring agreement
# across keys is much closer to what a listener means.
#
# The weights are combined over PERCENTILES, not raw scores: cosine and
# euclidean are not on the same scale, and a weighted sum of them would let the
# wider-spread metric dominate for reasons unrelated to similarity. Measured on
# the live corpus, anything from 30/70 to 70/30 returns the same top results --
# tracks strong on both dominate any middle weighting -- so 50/50 needs no
# tuning to be defensible.
BLENDED_AXES: dict[str, dict[str, float]] = {
    "best_match": {"embedding": 0.5, "groove": 0.5},
}

# This table and contract AXES must list the same ids: /axes serves the
# contract list while /recommend validates against this one, so if they drift
# the client renders a button that 400s. Fail at import, not at request time.
_contract_ids = {a["id"] for a in AXES}
_served = set(AXIS_FEATURES) | set(BLENDED_AXES)
assert _served == _contract_ids, (
    f"axes.py {sorted(_served)} != contract AXES {sorted(_contract_ids)}"
)
assert not (set(AXIS_FEATURES) & set(BLENDED_AXES)), (
    "an axis is either single-key or blended, not both"
)
