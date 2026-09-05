---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:37d2721ba7e8213fc74d14dd3c27d22b77263bf9777ff5edd8be427cde4bcbd6'
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

CENSUS VALUES LANDED. `AeatSyncWorkspaceCensusRowV1` carries `local_value` and
`aeat_value`, bounded at 256 characters, and the census screen renders them.
`None` on either side is UNOBSERVED and is WORDED as such -- a censo field the
taxpayer genuinely left blank is the empty string, and a blank cell beside a
populated one would read as "AEAT holds nothing" when the truth before a pull
is that nobody looked.

A CONFLICT row must now carry both values. The status is a claim ABOUT two
values, and making it while withholding one asks the operator to accept a
difference they cannot see -- the same defect the invoice/entry suggestions had.
UNSET and UNCHANGED stay unconstrained, because they are meaningful before
either side is read and requiring values there would force a producer to invent
them.

TWO OF MY OWN GATES CAUGHT THIS WORK, and both were right.

The S424 structural gate refused the new fields: it asserted no row may carry
free text, which was the retired redaction policy's structural form. The
exemption is now explicit and named, and it has a consequence worth stating --
the byte scan beside it was recorded as unfailable because no row could hold
prose. It CAN fail now: `local_value` is a real route, and that scan is the
check which catches protected prose arriving through it.

The overflow gate refused the extra columns at 80 and 100. The census screen now
takes columns in priority order, and a first ordering ranked the raw values
ABOVE the status -- which the census-adoption test caught, correctly. The values
are the evidence; the status is the VERDICT, and an operator who cannot see
whether a field is adopted or in conflict has lost the thing that tells them to
act. Status now outranks both.

The value pair is atomic: both or neither. One column headed "Local value" with
nothing beside it reads as a value AEAT does not hold rather than a column the
terminal had no room for.

The pair gate first passed WITH the splitting defect in place, because at 80
neither value fits and at 120 both do -- no tested width could tell an atomic
take from a greedy one. Width 100 was added because it is the only shape where
exactly one fits, and the defect then fails with `at 100 columns the census
shows half a comparison: ['category', 'field', 'local_value', 'status']`.
Restored by copy; 97 passed.

STILL OPEN: evidence-comparison and reconciliation rows carry no values, and
the AEAT side of every census row stays unobserved until a pull.
