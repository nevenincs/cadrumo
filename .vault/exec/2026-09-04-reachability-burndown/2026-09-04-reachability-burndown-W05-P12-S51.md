---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:a7cb81e0235fa9af340760fb2c00cfe98e59136434ff78d2937dc703e8bda4a6'
step_id: 'S51'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Test whether the producer-replaced-by-a-constant shape is gateable and record that it is not: matching a field annotation against an unreached producer's return type yields 3844 candidates when builtins are included and 227 when they are excluded, but the shape alone is not the defect, since the discriminating condition is that EVERY construction site passes the literal, and the leading candidate fails it because two of three sites pass a computed work unit id; adjudicate the work-address resolvers the investigation settled, displaced by a resolution that already carries what they return

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

No gate was added for the producer-replaced-by-a-constant shape, and the reason
is the cost of the discriminating half. Finding fields whose type an unreached
producer returns is cheap and useless: 3844 matches with builtins included, 227
with them excluded, because an optional field defaulting to None is ordinary.
The defect requires that NO construction site ever passes a computed value,
which needs every construction site of every model resolved. The leading
candidate failed exactly there -- two of three sites pass a real work unit id.
The two confirmed instances were found by reading the consumer, not by scanning.
