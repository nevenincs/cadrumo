---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S69'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P18.S69`

Scope: `src/aeat/domain/renta/_ledger_expenses.py` and
`src/aeat/domain/transactions/test_gross_invariant.py`.

## Description

- Added an explicitly typed `Literal["EUR"]` currency default for Renta
  expense facts and observations.
- Retyped the Renta finite-Decimal guard to accept `object`, preserving the
  runtime bool/non-Decimal rejection while clearing impossible static checks.
- Narrowed optional transaction tax-substrate fields before summing them in the
  non-EUR gross-invariant test.

## Outcome

The focused Renta/transaction Decimal residual bucket is closed. The touched
slice reports zero Ty diagnostics and zero Pyright errors or warnings.

## Notes

Verification:

- `uv run --no-sync ty check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --output-format concise`
- `uv run --no-sync pyright src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --level warning --warnings`
- `uv run --no-sync pytest src/aeat/domain/transactions/test_gross_invariant.py src/aeat/domain/renta/test_first_slice_routing.py -q`
- `uv run --no-sync ruff check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py`
