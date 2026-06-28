---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-audit]]"
---



# `ledger-renta-pipeline` `phase3-step1-deductibility-models` `phase3-step1-deductibility-models`

Completed Phase 3 strict Renta ledger-expense observation models and
deductibility evaluator.

- Created: `src/aeat/domain/renta/_ledger_expenses.py`
- Created: `src/aeat/domain/renta/test_ledger_expenses.py`
- Modified: `src/aeat/domain/renta/__init__.py`
- Modified: `2026-05-08-ledger-renta-pipeline-plan`
- Created: `2026-05-08-ledger-renta-pipeline-audit`
- Regenerated: `ledger-renta-pipeline.index`

## Description

Implemented the first pure domain surface for the ledger-to-Renta
pipeline:

- Added `ledger_renta_expense_aggregation` as the exported source-kind
  constant for the first Renta expense binding source.
- Added first-slice Modelo 100 category-to-casilla mapping for
  `cuotas_autonomos_ss`, `arrendamiento_local`, `asesoria_*`,
  `gastos_bancarios`, and `gastos_financieros`.
- Added strict frozen Pydantic models for deductible expense facts,
  deductibility context, deductibility results, and binding-ready
  Renta expense observations.
- Added category normalization to closed `SpendingCategory` members.
- Added a pure evaluator for full deductible, fixed percentage, usage
  ratio, statutory cap, non-deductible, and exclusive-use
  proportionality rules.
- Preserved source ids, invoice ids, dates, signed gross/deductible
  amounts, non-deductible amounts, category family, proportionality
  kind, applied ratio, legal citations, invoice evidence status, and
  reconciliation status.
- Added model guards so direct construction cannot mismatch category
  family or first-slice target casilla.

This phase intentionally does not load transaction or invoice
repositories and does not add registry bindings. Those are Phase 4 and
Phase 5 responsibilities.

## Tests

Verification completed:

- `uv run pytest src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/test_substrate.py`
- `uv run ruff check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/domain/renta/__init__.py`
- `uv run ty check src/aeat/domain/renta`

VaultSpec validation was run after regenerating the feature index.

- `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`
- `uv run vaultspec-core vault check frontmatter`
- `uv run vaultspec-core vault check body-links`
- `uv run vaultspec-core vault check links`
