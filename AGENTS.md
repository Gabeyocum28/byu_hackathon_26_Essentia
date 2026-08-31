# Working agreement

This is a 4-person, 24-hour sprint. Four people are running coding agents
against this repo at the same time. The full design is
`Essencia_design_spec.md` — read the section for your lane before coding.

## Ownership

You own exactly ONE of these folders. It was named in your task.

  ios/                                  — the iPhone app
  src/music_recommendations/server/     — the FastAPI backend
  src/music_recommendations/corpus/     — the Deezer crawler
  src/music_recommendations/analysis/   — the Essentia pipeline

You also own the matching folder under tests/ and any script in scripts/
that drives your lane.

Do not create, edit, or delete files outside the folder you own. This
includes pyproject.toml: if you need a dependency added, ask.

## contract/ is read-only

Everything in contract/ is shared by four people. Do not edit it.

If the contract appears wrong, incomplete, or blocking, STOP and tell the
human. Do not work around it. Do not add a field. Do not rename anything.
A contract change requires all four people to agree, and routing around a
mismatch silently breaks three other people's work.

## Test data

contract/fixture.json holds 30 real jazz tracks with real Deezer preview
URLs. Use it for all testing. Do not invent your own test tracks.

## Scope

This is a 24-hour sprint. Build what is asked, nothing more. No profile
screens, no explanation text, no accounts, no persistence beyond Redis,
no deployment config. If you think something extra is needed, ask.

## legacy/ is frozen

legacy/ holds the pre-spec MVP. Copy from it if useful; never import it,
never edit it.

## Merging

Commit and push small changes often. Do not sit on large diffs. Never
commit directly to main; branch as <name>/<topic> and open a PR. Run
`python3 -m pytest` before committing.
