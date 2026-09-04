---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6b9b9b4f7d5969a5d7022668bc41fb7d2555c86a64820f5606ab905a71a7b504'
step_id: 'S11'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Extend the ratchet to unused symbols and orphaned test modules with detector-teeth proof

## Scope

- `dev/quality`

## Changes

- `A` `dev/quality/unused_symbol_ratchet.py`
- `A` `dev/quality/unused_symbol_ratchet.toml`
- `M` `justfile`
- `M` `dev/quality/suite.py`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/unused_symbol_ratchet.py` -> `pass`

## Notes

The false green this campaign was built to close is now gated. The module ratchet
adjudicates modules no console script reaches and says nothing about a symbol inside a
module that IS reachable, nor about a test whose every shipped subject is a finding. Those
two populations -- 555 exact-confidence symbols across 315 modules, and 23 orphaned test
modules -- sat outside every gate, so the suite reported green over them.

The baseline records a COUNT per module rather than a list of names. Names churn as code
moves; a count answers the question the gate exists to ask, which is whether a reachable
module started carrying unused code. It fails in four directions, each proven: a module
absent from the file while carrying findings, a module carrying more than recorded, a
module carrying fewer than recorded, and a recorded module carrying none. The last two
matter as much as the first: they are how paid debt gets recorded rather than silently
absorbed, which is what keeps the file shrink-only.

Only the `exact` tier is ratcheted. `name-match` and `name-match-data` findings are members
reached by attribute access the scan cannot bind to a type, so gating them would ratchet
guesses rather than facts. That is why the gated number is 555 rather than the headline
1384, and the headline is not the actionable population.

The `cadrumo.entrypoints.tui` prefix is out of scope here exactly as in the module ratchet,
so its churn cannot fail a gate its own campaign owns.

Wired into `just check-unused-symbol-ratchet` and into the static-check suite, so it runs
where the module ratchet already does rather than only on request.

## Notes on what this is not

This is a backlog made visible, not a tolerance. The file's header states that the correct
response to a failure is never to raise a number, and the gate's own failure text repeats
it at the point of failure. Every entry that leaves the file is progress that had to be
recorded to pass.

The module ratchet remains RED on `cadrumo.domain.contabilidad` and
`cadrumo.domain.is_compensation` from concurrent work, unchanged and still not this
campaign's breakage. The new gate is green independently of it, so the two failures stay
distinguishable.
