---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8cbd594a68ef092d8d004c8697144af17edc99abf6376b860fccb33aed9a42c5'
step_id: 'S409'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give Home's actions, resumable declarations, agenda, evidence and messages zones their installed readers. All five are hard-coded UNAVAILABLE in the secure generation input, so the production Home an operator meets is five refusals and a Ledger summary. The application authorities the accepted due-driven decision names -- next actions, backlog, agenda, calendar evidence, notification snapshots -- exist and nothing yet calls them.

## Scope

- `src/cadrumo/application/workbench_generation.py`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `verify:` `pytest -n0 -m '' application/tests/test_workbench_generation.py tui/tests/test_home.py` -> `pass` (23)

## Notes

Step left OPEN: two of Home's six zones are now wired, four remain refused.

Landed. The AGENDA zone reads the real overview agenda, and the LEDGER zone now
reads the Ledger workspace projection the generation door already builds --
`_read_ledger` ran and its result was discarded on the way to Home, which is
what "nothing yet calls them" meant here: the authority was not missing, the
call was.

The interesting part is the refusal rule rather than the wiring.
`LedgerWorkspaceAreaStateV1.item_count` is a plain integer, so an area nobody
measured reports 0 -- the same value a genuinely empty area reports. The Ledger
workspace keeps those apart through `status` and renders UNMEASURED as
"Sin medir" rather than a digit. Home has no such room: its readiness block is
four bare numbers, and a zero there reads as a finding. So the block refuses
when ANY of its four areas is unmeasured rather than publishing three real
counts beside one fabricated one -- partial truth in a summary is
indistinguishable from whole truth once rendered.

Teeth proven by accepting unmeasured areas: `an unmeasured entries area still
produced a readiness block, so Home renders a zero nobody measured`. Restored
by copy and verified.

Remaining and NOT done: actions, resumable declarations and messages. All
three were measured rather than re-labelled, and they are blocked for three
DIFFERENT reasons, which one word was hiding.

ACTIONS -- blocked on a taxonomy decision. `HomeNextAction` is built only by
the fixture; the authority the plan names, `build_overview_status_next_steps`,
emits `OverviewStatusNextStepId` values (CREATE_PROFILE, IMPORT_TRANSACTIONS,
REPAIR_STORAGE) which are `overview status` CLI guidance, not Home's task
vocabulary. Home resolves `tui.home.reason.<code>` and declares six codes, all
about declaration review, ledger classification and evidence. Bridging the two
means deciding what Home's actions zone MEANS and minting reason codes plus
copy for it; guessing renders the degraded generic line the fixture gate now
catches.

DECLARATIONS -- blocked on a state mapping. The join itself is available: the
ref lacks a display name but `WorkUnit.name` has one and the door already holds
the catalogue, so the earlier note calling this blocked on a missing name was
half wrong. What is genuinely missing is the mapping. `WorkUnitState` has two
values (BORRADOR, DESCARTADO) and `HomeDeclarationState` has five; FILED and
DISCARDED fall out of facts the projection carries, but READY versus
NEEDS_REVIEW needs a grounded rule over `CalculationRevisionState`. Telling an
operator a declaration is READY when it needs review is a filing-grade harm, so
this refuses rather than guesses.

MESSAGES -- blocked on a pull, like S408. `PersistedNotificationsSnapshot` is
the record of an AEAT notifications capture; before any pull there is no
snapshot to read. The honest improvement available without a pull is a more
precise refusal: the current reason code says the reader is unavailable, which
is false -- the reader exists and the data does not. That is the next
actionable slice here.
