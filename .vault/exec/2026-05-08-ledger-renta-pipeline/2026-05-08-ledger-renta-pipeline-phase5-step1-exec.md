---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase5-review-audit]]"
---



# `ledger-renta-pipeline` `phase5-registry-binding-and-calculation-integration` `phase5-step1`

Completed the first registry/calculation integration slice for
ledger-derived Renta deductible expenses.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_common.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/aggregation/test_renta_ledger.py`
- Modified: `registry/aeat/modelos/100/revisions/2025.toml`
- Created: `src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py`
- Modified: `2026-05-08-ledger-renta-pipeline-plan`

## Description

Added the registry binding source kind
`ledger_renta_expense_aggregation` and a strict selector for the
first Modelo 100 direct-estimation expense slice. The selector binds
annual Modelo 100 period `0A` observations by target casilla and
supports only the `deductible_amount_sum` fact through `sum`
aggregation.

Bound the current first-slice 2025 Modelo 100 casillas:

- `0186` for self-employed social security.
- `0192` for premises rent and royalties.
- `0199` for independent professional services.
- `0203` for financial expenses.

The registry resolver converts typed
`RentaDeductibleExpenseObservation` rows into binding values, and the
CLI filing input aggregator now loads the persisted transaction and
invoice catalogues for annual Modelo 100, runs the repository-backed
Renta aggregation, resolves ledger Renta binding values against the
selected registry snapshot, and returns only the casilla inputs owned
by that ledger slice.

The calculation runtime remains repository-free. Tests run the
calculation with explicit casilla inputs, binding values, relation
values, and filing date context.

## Tests

Verification completed:

- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/application/aggregation/test_renta_ledger.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/renta/test_ledger_expenses.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/__init__.py src/aeat/application/aggregation/test_renta_ledger.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/__init__.py src/aeat/application/aggregation`
- `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`
- `uv run vaultspec-core vault check frontmatter`
- `uv run vaultspec-core vault check body-links`

The broader legacy filing test selection containing
`src/aeat/application/filing/test_modelo_303_390.py` initially failed
because those tests still expected Modelos 303 and 390 to be absent
from the registry, while the current shared workspace registry now
contains them. That follow-up audit and remediation is recorded in
`2026-05-08-ledger-renta-pipeline-phase5-step2`.

Review recorded in `2026-05-08-ledger-renta-pipeline-phase5-review`.
