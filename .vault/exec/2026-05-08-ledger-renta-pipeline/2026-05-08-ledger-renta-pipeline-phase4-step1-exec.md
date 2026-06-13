---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase4-review-audit]]"
---



# `ledger-renta-pipeline` `phase4-repository-backed-aggregation` `phase4-step1`

Completed the first repository-backed aggregation slice from persisted
ledger and invoice catalogues into Renta expense observations and
binding-ready casilla totals.

- Created: `src/aeat/application/aggregation/_renta_ledger.py`
- Created: `src/aeat/application/aggregation/test_renta_ledger.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/domain/transactions/_repository.py`
- Modified: `src/aeat/domain/invoices/_repository.py`
- Modified: `2026-05-08-ledger-renta-pipeline-plan`

## Description

Added `aggregate_renta_ledger_expenses` for pure catalogue aggregation
and `aggregate_renta_ledger_expenses_from_repositories` for loading
the persisted encrypted transaction and invoice catalogues before
aggregation.

The service applies the Phase 2 first-slice contract:

- Annual Modelo 100 periods only.
- Linked invoice issue date is the filing date when invoice evidence is
  present; transaction value date or booked date is used otherwise.
- The transaction is the counting unit and linked invoice facts enrich
  evidence, base, IVA, and date fields without double counting.
- First-slice category mapping is limited to the approved Modelo 100
  casillas for autonomo social security, premises rent, advisory
  services, and financial or bank expenses.
- Business transactions use the full absolute transaction amount;
  mixed transactions apply `business_pct` before Renta proportionality
  evaluation.
- Linked incoming transactions become negative refund observations
  only when they preserve a linked invoice and category.
- Missing categories, unsupported categories, unsupported directions,
  personal or unclassified rows, reconciliation mismatches,
  multi-transaction invoice links, amount mismatches, out-of-period
  rows, and ineligible proportionality results are emitted as typed
  aggregation issues.
- Unsupported non-EUR rows and invalid fact shapes are emitted as
  typed issues before reaching formula input surfaces.

The domain repositories now accept an optional real
`SecureObjectRepository` dependency. The default production behavior is
unchanged; tests and future application entrypoints can inject a
real SQL-backed secure object repository without changing global
database settings.

## Tests

Verification completed:

- `uv run pytest src/aeat/application/aggregation/test_renta_ledger.py`
- `uv run pytest src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/test_substrate.py -q`
- `uv run ruff check src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py`
- `uv run ty check src/aeat/application/aggregation src/aeat/domain/renta src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py`

The aggregation tests include an encrypted repository round trip using
real `TransactionCatalogueRepository`, `InvoiceCatalogueRepository`,
`SecureObjectRepository`, SQLite, and ephemeral key providers.

Review recorded in `2026-05-08-ledger-renta-pipeline-phase4-review`.
