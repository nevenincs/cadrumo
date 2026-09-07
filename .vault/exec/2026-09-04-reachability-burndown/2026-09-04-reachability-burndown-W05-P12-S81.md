---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:00fb35328fbd80bddaac7ebc0b9d797fe9d0dfabe04ecd84eec9836212babcea'
step_id: 'S81'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Make the module ratchet report what it carries when it passes, since the intentional dispositions and derived deferrals are excluded from both failure directions by design and the passing path is therefore the only one that can ever show them to an operator, yet it printed nothing at all: seven accepted exceptions and two deferred clusters were invisible exactly when nothing else was wrong, which teaches a reader that green means empty. Print the same report on stdout on the clean path and cover it with a verdict-level case plus a control for a tree that carries nothing.

## Scope

- `dev/quality/unreachable_module_ratchet.py`
- `dev/tests/test_unreachable_module_ratchet_gate.py`

## Changes

- `M` `dev/quality/unreachable_module_ratchet.py`
- `M` `dev/tests/test_unreachable_module_ratchet_gate.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` a clean `python -m dev.quality.unreachable_module_ratchet` now names
  seven intentional dispositions and two deferred clusters on stdout, exit 0
- `verify:` `pytest .../test_unreachable_module_ratchet_gate.py -k clean_verdict`
  2 passed
- `verify:` `ruff check` and `ty check` clean
- `verify:` unused 1040, exact 411, unadjudicated 218 -> 215

## Notes

The gate's own contract says intentional entries "must remain reported" and are
"carried separately so they cannot disappear into the actionable backlog". They
are excluded from both failure directions, which means the passing path is the
ONLY path that can report them -- and it wrote nothing. Every green run in this
campaign said less than it knew.

This is the standing instruction in the campaign brief made structural: never
treat a green ratchet as a zero backlog. Until now that was discipline a reader
had to supply; the tool now supplies it.

Found while investigating a transient `ratchet=1` that was green on the next
run. The peer was mid-edit across several application modules, and a module in
flux can look unreachable for one pass. Chasing the flap is what surfaced that
the clean path is silent, which is the more durable finding: a gate printing
nothing is indistinguishable from a gate that did nothing, and I had been
reading exit 0 as evidence for several iterations.
