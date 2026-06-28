---
tags:
  - '#audit'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
---



# `ledger-renta-pipeline` audit: `phase3-code-review`

## Scope

Phase 3 production and test changes for the strict Renta
ledger-expense observation and deductibility evaluator surface.

Reviewed files:

- `src/aeat/domain/renta/_ledger_expenses.py`
- `src/aeat/domain/renta/__init__.py`
- `src/aeat/domain/renta/test_ledger_expenses.py`

## Findings

No open findings after review.

Review hardening applied before this audit was finalized:

- `RentaDeductibilityResult` now validates that `category_family`
  matches `category`.
- `RentaDeductibleExpenseObservation` now validates that
  `category_family` matches `category`.
- `RentaDeductibleExpenseObservation` now validates that
  `target_casilla` matches the first-slice category mapping.

## Recommendations

Proceed to Phase 4 repository-backed aggregation. Keep the Phase 3
models pure and side-effect-free; repository loading should remain
outside the Renta domain models.

Verification completed:

- `uv run pytest src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/test_substrate.py`
- `uv run ruff check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/__init__.py`
- `uv run ty check src/aeat/domain/renta`
