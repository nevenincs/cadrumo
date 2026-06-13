---
tags:
  - '#audit'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase5-step1-exec]]"
---



# `ledger-renta-pipeline` Code Review

## Scope

Phase 5 registry binding and calculation integration.

Reviewed files:

- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_validate.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/application/filing/__init__.py`
- `src/aeat/application/aggregation/test_renta_ledger.py`
- `registry/aeat/modelos/100/revisions/2025.toml`

## Findings

PHASE5-001 | MEDIUM | CLI aggregation used the strict all-bound-casilla resolver

The initial Phase 5 CLI route used the generic
`resolve_bound_casilla_inputs` helper against the full Modelo 100
revision. That helper correctly requires every bound casilla in the
revision to have a supplied binding value. Modelo 100 already has
profile-bound fields, so the ledger-only route failed on missing
profile binding values before returning the Renta expense casillas.

Status: resolved.

Resolution:

- Kept `resolve_bound_casilla_inputs` strict for full binding
  materialisation.
- Added a CLI-local projection that returns only casillas whose
  binding value is available from the Renta ledger aggregation slice.
- Added a repository-backed CLI aggregation test that verifies the
  Renta ledger route returns `0186`, `0192`, `0199`, and `0203`
  without requiring profile bindings.

## Result

No open findings remain after review.

Verification completed:

- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/application/aggregation/test_renta_ledger.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/renta/test_ledger_expenses.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/__init__.py src/aeat/application/aggregation/test_renta_ledger.py`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/__init__.py src/aeat/application/aggregation`
