---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:b4670723c028a4cc56a6a22a7416df6b7341b32a7f268d5a143235f2394029a8'
step_id: 'S408'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

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

Two zones gained their local reader. Two remain refused, and the refusals now
say something the previous ones did not.

CENSUS. The projection contract made pre-pull census rows UNPUBLISHABLE: every
census row required both LOCAL_PROFILE and AEAT_CENSUS to be observed, and the
AEAT side is never captured before a pull. So the zone could only ever be empty
beside a local source reporting a profile it had read -- exactly the pairing
this Step opens with.

The four census statuses are all VERDICTS: each claims someone compared the two
sides. Reusing one would have told the operator their address matches, or
conflicts, on the strength of an observation nobody made. UNSET is the closest
trap -- it reads like "nothing here" but says the FIELD has no value, not that
nobody checked. NOT_COMPARED is the missing state, and with it the AEAT-source
requirement narrows to rows that actually claim a verdict.

Rows come from CENSAL_ADOPTABLE_PATHS, the authority on which profile paths an
AEAT censal read can speak to at all. A path list written here instead would
produce rows a real pull could never fill; an import-time check fails if the
two ever drift. One row per path INCLUDING the paths the profile leaves blank,
because the blank field is the one a pull is most likely to change. A path the
record does not carry is the empty string -- observed and blank -- never None,
which on this row means nobody looked and is false of a record this session
read to build the row at all.

NOTIFICATIONS. Custody is read now (the count reader composed earlier), but the
overview row still reported the local side as never observed, so an observable
count of zero sat beside a row claiming nobody looked. Both cannot be true and
the count is the one backed by a read. Whether custody was read is a fact about
the SESSION rather than about the area, so it is decided per call rather than by
the static area set: no reader composed stays NOT_OBSERVED, zero documents is
ABSENT, documents present is PRESENT.

STILL REFUSED, with reasons that are now specific. Notification ROWS need
issued_on, read_state and category; the custody record carries certificado_id,
attachment digest, byte size, source URL and fetch time, and none of the three.
That is a genuine absence of local authority for the row shape, not an
uncomposed reader. LOCAL_RECONCILIATION has no authority anywhere in the
codebase; nothing records a local reconciliation decision, so there is nothing
to read.

Teeth, four defects each caught by its own gate: local_value falling back to
None (blank collapses to unobserved), dropping rows for absent paths, publishing
a verdict without the AEAT observation, and allowing a NOT_COMPARED row to carry
an AEAT value. The custody defect -- claiming an unread store as observed --
failed 15 tests. All restored by copy, defect count 0. 140 passed.

## Notes

REGRESSION FOUND AND FIXED, mine. The census value invariant added under S422
rejected the devtools workbench fixture, which built a CONFLICT row carrying
neither value. Every aeat-sync workbench fixture surface raised ValidationError
on build. The fixture now carries the two addresses it claims to be comparing,
which is what a conflict row is for. Nine responsive checks pass.

Ten dev/locales failures are pre-existing and not from this change: none names
the added key, and the two inspected closely fail on production files this
change does not touch -- a new unsanctioned language-override site at
entrypoints/tui/destination_session.py::run_requested_destination, and a
scanner regression on flows.progress.required. 646 passed alongside them.
