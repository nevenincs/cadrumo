---
tags:
  - '#exec'
  - '#core-authority'
step_id: S25
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P08.S25 — RENAME-006 ripgrep gate: BLOCKED

## Blocking Condition

The plan's own execution gate "verify zero callers via ripgrep" was not
satisfied. The five constants in `application/aggregation/_shared_issue_reasons.py`
are not dead — they are used as StrEnum member values in two consumer enums:

- `_iva_ledger.py` lines 70-74: `IvaLedgerAggregationIssueReason` assigns all
  five as enum members via `= _shared_issue_reasons.<NAME>`.
- `_renta_income_ledger.py` lines 51-55: `RentaIncomeLedgerAggregationIssueReason`
  assigns all five as enum members.
- `_renta_ledger.py`: similar pattern.

The constants serve as the string values backing these StrEnum declarations.
Deleting them would break the enum value assignments in all three ledger files.

## Resolution

Step left unchecked. No code changes made. These are shared StrEnum backing
values, not dead constants. The tracker's "zero consumer" claim was incorrect.
Deferred to a future campaign.
