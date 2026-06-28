---
tags:
  - '#audit'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase4-step1-exec]]"
---



# `ledger-renta-pipeline` Code Review

## Scope

Phase 4 repository-backed aggregation implementation and tests.

Reviewed files:

- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/aggregation/__init__.py`
- `src/aeat/application/aggregation/test_renta_ledger.py`
- `src/aeat/domain/transactions/_repository.py`
- `src/aeat/domain/invoices/_repository.py`

## Findings

PHASE4-001 | MEDIUM | Malformed ledger facts could escape issue collection

The initial aggregation implementation constructed
`RentaDeductibleExpenseFact` outside an error boundary and did not
reject non-EUR source rows before building a fact with the Renta
domain default currency. A zero mixed-business amount or unsupported
currency could therefore raise during aggregation or produce an
incorrect EUR observation path.

Status: resolved.

Resolution:

- Added explicit unsupported-currency issue handling before fact
  creation.
- Wrapped fact creation and observation building so validation errors
  become bounded `INVALID_LEDGER_FACT` issues.
- Added tests for non-EUR source rows and zero mixed-business amounts.

## Result

No open findings remain after review.

Verification completed:

- `uv run pytest src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/test_substrate.py -q`
- `uv run ruff check src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py`
- `uv run ty check src/aeat/application/aggregation src/aeat/domain/renta src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py`
