---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:c8155d77d6db2814bf78d8a1f3f18ace2fe48fd50a9303629abc6019b90b1e64'
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

CORRECTION to the next-slice estimate. This record, and the report that
followed it, called composing `list_documents` into the reader the one
remaining mechanical item. It is not mechanical, and the shape is worth
recording so the estimate is not made a third time.

`NotificationDocumentService` cannot be what the door composes: its constructor
takes six ports including a `document_fetcher`, and a read-only pre-pull
generation door must not acquire network capability to count local records.
`list_documents` in fact needs only `repository_factory(bucket_id).list_snapshots()`,
so the door needs the REPOSITORY, which matches how it takes every other
dependency.

That repository is not composable from here today. Its construction is roughly
eighteen lines of adapter configuration -- namespace definition, object key,
two error factories, domain label -- and it lives inside
`entrypoints/cli/_app_live_notifications_cli.py`. Duplicating it in the TUI
launcher would create a second definition of the same thing, which
`aeat-architecture-boundaries` forbids; the correct move is to promote it to a
canonical public module and have both entrypoints import it.

So the work is: promote the factory, inject it as a narrow reader callable
matching `account_session_reader`'s existing shape, thread the count through
the reader, extend the capture-coherence guard to cover the new read, and gate
all of it. That is an architecture change touching a CLI entrypoint another
writer is actively committing in, not a call added to an existing composition.
Deliberately not started rather than begun and left half-applied, which would
leave the coherence guard inconsistent.
