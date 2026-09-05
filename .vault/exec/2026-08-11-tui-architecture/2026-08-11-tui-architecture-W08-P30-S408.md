---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:a4e1ad012f1582b4181fcffcf088170801051cc40b47034d5261526ac231b698'
step_id: 'S408'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Give AEAT Sync its local row readers, or state per zone why the local authority cannot be read. The installed workspace projects overview rows only: census, filed-declaration, notification, evidence-comparison and reconciliation rows have no installed reader, so LOCAL_PROFILE and LOCAL_FILINGS report observable counts beside zones that carry no rows, while LOCAL_NOTIFICATION_CUSTODY and LOCAL_RECONCILIATION are UNAVAILABLE outright. The refusals are honest today; a workspace whose local side is permanently empty is not the target state.

## Scope

- `src/cadrumo/application/aeat_sync/workspace_reader.py`

## Changes

- `A` `src/cadrumo/adapters/persistence/profile/notification_documents.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`
- `M` `src/cadrumo/application/aeat_sync/workspace_reader.py`
- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `verify:` `pytest -n0 -m '' application/aeat_sync/tests application/tests/test_workbench_generation.py tui/aeat_sync/tests` -> `pass` (112)

## Notes

The notification-document repository was composed inline in the CLI entrypoint
-- namespace, object key and two error factories -- so a TUI read could only
have duplicated it. It now has one canonical home,
`adapters/persistence/profile/notification_documents.py`, and the CLI imports
it: a TUI read and a CLI write cannot end up pointed at different stores.

AEAT Sync's LOCAL_NOTIFICATION_CUSTODY source now reports a real count, read
through that same factory. The reader takes only the count -- AEAT Sync needs
to know whether anything is held, not what it says, and decrypting document
payloads to answer that would be a disproportionate read.

Three states stay distinct where there were two. An UNBOUND reader is a
composition gap (`local_reader_not_composed`); a bound reader answering ZERO is
a proven zero the operator can act on; a positive count is what is held.
Collapsing the first two would tell an operator their custody is empty on the
strength of nobody having asked.

The count is read inside the capture window and re-read at its close, joining
the other sources under the coherence guard: a document landing mid-capture
would otherwise let AEAT Sync publish a count that was never true at any single
instant.

Teeth proven by coercing an unread store to zero (`custody_count or 0`): the
gate fails with `assert None == 'workbench.aeat_sync.local_reader_not_composed'`.
Restored by copy.

One pre-existing failure is NOT mine and not a regression:
`test_live_notifications_pull_persists_a_grounded_snapshot_and_no_remote_write`
refuses with `selected live test requires CADRUMO_LIVE_TESTS_ENABLED=1`. It is
an environment gate, not an assertion; 95 of 96 notification tests pass.

STILL OPEN: census, evidence-comparison and reconciliation rows carry no values
(item 4), and LOCAL_RECONCILIATION still has no authority anywhere -- its
`local_row_reader_unavailable` refusal remains correct.
