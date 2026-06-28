---
step_id: S43
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P14.S43 — ParityStatus collapse BLOCKED (RENAME-003 false-positive)

## Decision

Step blocked. The two `ParityStatus` declarations have distinct member sets:

- `_parity_tapes.py:26` — `Literal["match", "mismatch"]` (2 members; tape run outcomes only)
- `_workbook_parity.py:57` — `Literal["match", "mismatch", "not_run"]` (3 members; includes pre-run state)

The `"not_run"` variant is used in `_workbook_parity.py:924` as the default for `WorkbookParityRunReport.run_status` when a workbook has not been executed. Collapsing to `_parity_tapes.py`'s 2-member type would either require adding `"not_run"` to a tape-concept type that has no use for pre-run state, or removing `"not_run"` from the workbook-scanning contract, breaking the run-status logic.

## Rationale

Same false-positive pattern documented for W04 (CalendarCCAA, ProfileFactValue, IVA mapping). The audit surface matched names; the member sets diverge by one domain-meaningful variant. Consistent with the W04 lesson: read both declarations and check consumer contracts before collapsing.

## Commit

`62f3c5b92` — docs(registry): block S43 ParityStatus collapse - domain-divergent false positive
