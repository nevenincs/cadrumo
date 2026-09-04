---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:f3726241f972849729bcbd109d1a5686b809ee586f467bb95effa1fee36b40da'
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

Remaining and NOT done: actions, resumable declarations and messages. Each
needs its authority identified and its refusal semantics settled the same way
this one did, which is a step apiece rather than a sweep.
