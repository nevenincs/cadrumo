---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:60dc038b03230ce673e6124d82c6c3edf9c963d07eba9461fd3e99a4386691b2'
step_id: 'S422'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the AEAT Sync comparison rows the values they compare. DECIDED 2026-09-04: AeatSyncWorkspaceCensusRowV1 is documented as a row 'without values' and carries only a path, a category and a status, so the census surface cannot show what actually differs between the local profile and the AEAT record -- which is the entire purpose of a census comparison. Evidence-comparison and reconciliation rows have the same shape. Carry the local and observed values on each, and render them beside the existing status axis. Availability states stay distinct: showing a value must not collapse missing, never-captured and a proven zero.

## Scope

- `src/cadrumo/application/aeat_sync/workspace.py and src/cadrumo/entrypoints/tui/aeat_sync/screens.py`

## Changes

- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `M` `src/cadrumo/entrypoints/tui/aeat_sync/tests/test_aeat_sync_workspace.py`
- `verify:` `pytest -n0 -m '' application/aeat_sync/tests` -> `pass` (25)

## Notes

Step left OPEN. The step asks that census, evidence-comparison and
reconciliation rows carry the values they compare, and that half is BLOCKED,
not done. Those three row families have no production producer at all: the
reader supplies `overview` and `filed_declarations` only, and the AEAT side of
each is `NEVER_CAPTURED` until a pull happens, which is S408's remainder. Every
row of theirs on screen today comes from a fixture. Adding value fields now
would be contract surface with no producer and no authority behind it, so it
stays unsupported rather than guessed.

What the investigation DID find is a real silent under-declaration, fixed here.
A zone's item count was taken whenever ANY source was observable. That is right
for a LIST zone, whose count is of what one source holds, and wrong for a
COMPARISON zone, whose rows are discrepancies BETWEEN sources: with the AEAT
half never pulled, the local half's zero was published as the zone's count, so
the operator read "no discrepancies" where the truth was "no comparison has
been made". Comparison zones now require every source to be observable before
they report a count, and report never-observed otherwise. Measured before:
`evidence_comparison stale count=0`, `reconciliation stale count=0`. After:
both `unavailable count=None`, while the census zone keeps its genuine observed
zero.

A frozen-count gate was replaced rather than re-numbered. It asserted the
aeat_sync namespace held exactly 112 keys, so the two section headings added
for the vertical rhythm broke it while translating nothing. A count cannot
distinguish a key ADDED from a key LOST -- it fails identically for both -- and
it never checked the thing that matters. It now asserts that every literal
`tui.aeat_sync.*` leaf the package asks for exists in every locale, with
single-segment namespace prefixes excluded because the code completes those
from enum values at runtime. Teeth proven by removing one key from the Spanish
catalogue: one locale fails, three pass; restored by copy.

Teeth for the count rule proven by restoring the any-source condition, which
reproduced the exact `0` this step removes. A first attempt proved nothing:
the concurrent writer had already committed the fix, so the `git show HEAD`
copy used as the "before" baseline contained it. Verified the injected defect
was actually present before trusting the failure.

Pre-existing and NOT caused by this change, confirmed by running it against a
HEAD copy of the module: both parametrisations of
`test_completing_one_overview_operation_keeps_the_other_action_reachable` fail.
