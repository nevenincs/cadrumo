---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S17'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add the compact out-of-window summary model and partition field

## Scope

- `src/aeat/domain/transactions/_models.py and src/aeat/domain/transactions/__init__.py`

## Description

- Search the transaction domain model for the partition and out-of-window stub contract.
- Read `LedgerDatePartition`, `OutOfWindowTransactionStub`, the transaction repository protocol, and the public transaction facade before editing.
- Expand the S17 plan scope to include the public transaction facade required by the new domain type.
- Add `OutOfWindowTransactionSummary` with excluded count and min/max filing-date fields.
- Add an optional `out_of_window_summary` field to `LedgerDatePartition` while keeping the row-level `out_of_window` field for migration compatibility.
- Export `OutOfWindowTransactionSummary` through `aeat.domain.transactions`.
- Run domain ruff checks and a direct import/validation check.
- Audit the change and record that no open findings remain.

## Outcome

`LedgerDatePartition` now has an optional compact summary field for diagnostics-channel migration, and `OutOfWindowTransactionSummary` is available from the public transaction facade. The change is additive: current repository callers can continue consuming row-level stubs until S19 starts emitting summaries.

## Notes

The first ruff pass found only facade import and `__all__` ordering issues; `ruff --fix` corrected them. The final ruff check passed, and a direct import/validation command for `OutOfWindowTransactionSummary` passed.
