---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:da8980aa1fd0b952ebb0fed26d673a76d0fd7b9176db785109cad7ed91d8a395'
step_id: 'S408'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give AEAT Sync its local row readers, or state per zone why the local authority cannot be read. The installed workspace projects overview rows only: census, filed-declaration, notification, evidence-comparison and reconciliation rows have no installed reader, so LOCAL_PROFILE and LOCAL_FILINGS report observable counts beside zones that carry no rows, while LOCAL_NOTIFICATION_CUSTODY and LOCAL_RECONCILIATION are UNAVAILABLE outright. The refusals are honest today; a workspace whose local side is permanently empty is not the target state.

## Scope

- `src/cadrumo/application/aeat_sync/workspace_reader.py`

## Changes

- `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `verify:` `pytest -n0 -m '' application/aeat_sync/tests` -> `pass` (26)

## Notes

Step left OPEN: no new row reader is composed. What changed is that the
refusals now name their real condition, which is a prerequisite for composing
them and was actively misleading before.

One constant, `local_row_reader_unavailable`, covered two opposite situations.
For LOCAL_RECONCILIATION it is exactly right: nothing in the codebase records
local reconciliation decisions, so the work is to write an authority. For
LOCAL_NOTIFICATION_CUSTODY it is false.
`NotificationDocumentService.list_documents` reads local custody today and
answers before any pull -- with an empty tuple when custody is empty, which is
a proven zero rather than an absence. Calling that a missing reader sends
whoever picks the step up to write something already written. The gap there is
composition, and `local_reader_not_composed` says so.

The distinction is invisible on screen: both render as a refused source, so
nothing but the reason code carries it and nothing but a gate keeps the two
from collapsing back into one convenient constant. Teeth proven by emptying the
per-source table so both fall back to the generic refusal -- `notification
custody IS readable today, so calling its refusal a missing reader sends the
next person to write a reader that already exists`. Restored by copy and
verified.

Still true and unchanged: the AEAT half of every zone is NEVER_CAPTURED until a
pull, and census, evidence-comparison and reconciliation rows have no producer.
The next actionable slice is composing `list_documents` into the reader, which
also requires extending the capture-coherence guard to cover the new read --
deliberately not started here rather than left half-wired.

Pre-existing and NOT caused by this change:
`test_completing_one_overview_operation_keeps_the_other_action_reachable` fails
in both parametrisations. It was confirmed failing against a HEAD copy of the
module earlier in this campaign, passed once in an intervening run, and is
failing again; this change touches only local-source refusals and that test
builds its own all-AVAILABLE observations.
