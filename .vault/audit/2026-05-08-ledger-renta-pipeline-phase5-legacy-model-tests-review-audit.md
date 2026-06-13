---
tags:
  - '#audit'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase5-step2-exec]]"
---



# `ledger-renta-pipeline` Legacy Modelo Tests Review

## Scope

Reviewed the Phase 5 legacy-model test expansion and the new Modelo
303 and Modelo 390 declaration aggregation route.

Reviewed files:

- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/application/filing/test_modelo_303_390.py`
- `src/aeat/application/filing/test_complementaria.py`
- `src/aeat/application/filing/test_import.py`
- `src/aeat/entrypoints/cli/test_user_cli_surface.py`

## Findings

No open findings remain.

Resolved issue:

PHASE5-LMT-001 | MEDIUM | Legacy tests treated supported IVA models
as missing registry definitions.

The stale tests conflated filing behavior with absent-registry
behavior for Modelos 303 and 390. The current registry contains
committed definitions and binding tests for both models, so those
tests no longer described the production boundary.

Resolution:

- Replaced Modelo 303 and Modelo 390 absent-registry expectations with
  positive registry-backed draft, complementaria, import, and CLI
  calculation assertions.
- Kept an explicit unknown-model negative test for the unsupported
  registry boundary.
- Audited remaining absence assertions and confirmed they target
  unknown model, invalid snapshot, or parser-boundary behavior.

## Result

The updated tests are non-tautological: they assert registry snapshot
versions, calculated IVA totals, imported justificante metadata, and
CLI-projected invoice-derived IVA values rather than merely checking
that calls return successfully.

Verification completed:

- `uv run pytest src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py::test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices src/aeat/domain/invoices/test_iva_classification.py::test_invoice_line_observation_feeds_modelo_303_binding_resolver_end_to_end src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q`
- `uv run ruff check src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run ty check src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
