---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3a574f4317a0a57a59565499cc12f889fdf41ad47736ecaac4bdccf83b05199b'
step_id: 'S38'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Record the C1 exit governance fact as a vaultspec execution record

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`

## Changes

- `M` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W05-P10-S38.md`
- `verify:` `pytest test_c1_bounded_review.py -m integration` -> `11 passed`

## Notes

THE C1 EXIT FACT. The C1 accessibility matrix, production route and
availability fence are proven by the bounded-review conformance module
`src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py`, run on
2026-08-31 with `-m integration` and reporting 11 passed, 0 failed. The marker
matters and the row says so: the module carries the integration marker only, so
a `-m unit` run reports NOTHING RAN across every test in it and exits clean.

COUNT DRIFT, minor and stated rather than smoothed over: the row says 10 tests,
the module now has 11. The suite grew; nothing was removed.

COMMIT PROVEN AGAINST: HEAD `604a9c1bd4669fb0ae6d95aa5e9e3e5beb9b0934`. As with
the C1 cohort-open record, THE RUN WAS AGAINST THE WORKING TREE AT THAT HEAD
RATHER THAN A CLEAN CHECKOUT -- this worktree is shared and carried uncommitted
changes from concurrent lanes, so naming the commit alone would overstate what
was measured.

WHY THIS RECORD WAS REWRITTEN, and it is a sharper case than the cohort-open
record's. The previous body was headed "Emit and validate
`ModeloWorkspaceC1ExitReceiptV1` with the accepted-companion prefix, migration
evidence, denominator digest..." and asserted a verify line of
`validate_modelo_workspace_c1_exit_receipt(receipt, action_denominator_validator=...)`
`-> []`, explicitly annotated "real validator run, not hand-authored".

EVERY ARTIFACT THAT CLAIM DEPENDS ON IS GONE. `dev/quality/modelo_workspace_receipts.py`
does not exist. Neither `validate_modelo_workspace_c1_exit_receipt` nor
`ModeloWorkspaceC1ExitReceiptV1` is defined anywhere in `dev/` or `src/`. The
`.vault/reference/` receipt document the Changes section lists as added is not
in the vault. The 2026-08-28 amendment retired the code-resident receipt design
and marked its building rows (W01.P01.S02, S03) RETIRED BY AMENDMENT; this
record was left behind describing it.

WHAT MAKES THAT WORSE THAN STALE PROSE: this is a PERSISTED EXECUTION RECORD
asserting that a validator ran and returned clean. The annotation "real
validator run, not hand-authored" exists precisely to distinguish a genuine
verification from a claimed one -- and it now guarantees the opposite of what it
was written to guarantee, because the run it attests to cannot be reproduced by
anyone. A reader checking this row would find a record present, detailed, and
self-certifying, with nothing behind it.

STANDING GOAL NOT COVERED, restated so closure does not bury it: the retired
exit receipt bound the denominator digest and the accepted-companion prefix as
MACHINE-CHECKED fields. This record asserts the conformance module and commit in
prose. Nothing recomputes them and nothing fails if they drift.
