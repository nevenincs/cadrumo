---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:cc7972ef90483a45792ae2ea99c847dba3bd88ad3a09f061f4f97d29e7a38cf4'
step_id: 'S24'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Gate the unconsumed-export population so the owner review is not overtaken by growth, and triage it by area and by shape

## Scope

- `dev/quality/unconsumed_export_ratchet.py`

## Changes

- `A` `dev/quality/unconsumed_export_ratchet.py`
- `A` `dev/quality/unconsumed_export_ratchet.toml`
- `A` `dev/quality/tests/test_unconsumed_export_ratchet.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_unconsumed_export_ratchet.py` -> `pass`
- `verify:` `just check-unconsumed-export-ratchet` -> `pass`

## Notes

The 368 were inventoried but ungated: nothing stopped the number growing while
the owner review waited. The gate asks nobody to resolve them and refuses a new
one, which is the half needing no decision -- and the cheapest moment to ask who
imports a name is while its author still remembers exporting it.

Calibration mattered more than construction. Counting every exported name no
module imports gives 2247, mostly ordinary published API whose consumer is a
test or an external caller; a gate on that would fire on any new public
interface before its first importer landed. Intersecting with the reachability
audit narrows it to the population actually under review. A first narrowing
then gave 136 rather than 368, because it counted test modules as consumers
while the inventory does not -- two records disagreeing about what they count
is the defect class this campaign exists to remove, so the gate now excludes
tests as publishers AND consumers, matching the inventory exactly.

The ledger also gained two triage dimensions for whoever rules on the 368: by
area, and by shape. 72 of the 368 are single-return pass-throughs, which makes
each a cheaper decision because a reader sees what is behind it. Only ONE
delegates to a public member of its own argument -- the `find_invoice` shape
that made that symbol cheap to retire -- and that one documents why it exists.
So the population holds no further illusions of that kind: the 368 are
decisions, not deferred work.

Four faults in the gate were found by testing it rather than by reading it: two
`ty` diagnostics, one of which was a real correctness fix (an `__all__` entry
need not be a string); a lookup key hardcoded to the repository root, so the
function could only ever scan the real tree; an `evaluate` that ran a full audit
of the real repository when handed a fixture; and an edit that silently did not
apply because the target string had reformatted underneath it, leaving the old
call in place while it read as fixed.
