---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase5-step1-exec]]"
  - "[[2026-05-08-ledger-renta-pipeline-phase5-legacy-model-tests-review-audit]]"
---



# `ledger-renta-pipeline` `phase5-registry-binding-and-calculation-integration` `phase5-step2`

Completed the legacy Modelo 303 and Modelo 390 filing test audit that
was discovered during Phase 5 verification.

## Description

The initial Phase 5 broader filing check found stale tests that still
expected Modelos 303 and 390 to be absent from the active registry.
That assumption conflicted with the current committed registry state,
which already contains supported Modelo 303 and Modelo 390 registry
definitions, IVA binding declarations, and committed registry tests.

Updated the filing and CLI surfaces so the tests assert current
registry-backed behavior instead of registry absence:

- `src/aeat/application/filing/test_modelo_303_390.py` now verifies
  positive draft calculation for Modelo 303 and Modelo 390, with a
  separate unknown-model negative boundary.
- `src/aeat/application/filing/test_complementaria.py` now verifies
  Modelo 303 and Modelo 390 complementaria drafts against active
  registry snapshots and removes the computed Modelo 130 casilla from
  a manual-input fixture.
- `src/aeat/application/filing/test_import.py` now verifies Modelo 303
  justificante import creates a registry-backed draft and companion
  submitted filing record.
- `src/aeat/entrypoints/cli/test_user_cli_surface.py` now verifies the
  operator N26 and invoice tape builds a Modelo 303 registry draft from
  persisted invoice data.
- `src/aeat/entrypoints/cli/_common.py` now routes Modelo 303 and
  Modelo 390 filing aggregation through the existing IVA invoice-line
  observation bridge and ledger IVA binding resolver.

The CLI aggregation route keeps the registry calculation runtime pure:
repository loading, period filtering, invoice-line classification, and
binding-value materialisation happen before draft calculation.

## Legacy Test Audit

Searched for stale registry-absence expectations in tests using:

- `not present in the calculation registry`
- `requires_registry_definition`
- `requires_registry_snapshot`
- `without_registry_snapshot`
- Modelo 303 and Modelo 390 references in test files

Remaining absence tests target deliberately unknown models, invalid
snapshots, or parser boundary behavior. No remaining test asserts that
Modelo 303 or Modelo 390 is absent from the current calculation
registry.

## Tests

Verification completed:

- `uv run pytest src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py -q`
- `uv run pytest src/aeat/application/filing/test_import.py::TestImportFromJustificante::test_modelo_303_justificante_import_uses_registry_snapshot src/aeat/entrypoints/cli/test_user_cli_surface.py::test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices -q`
- `uv run pytest src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py::test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices src/aeat/domain/invoices/test_iva_classification.py::test_invoice_line_observation_feeds_modelo_303_binding_resolver_end_to_end src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q`
- `uv run ruff check src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run ty check src/aeat/entrypoints/cli/_common.py src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/domain/renta/test_ledger_expenses.py src/aeat/application/filing/test_modelo_303_390.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_import.py src/aeat/entrypoints/cli/test_user_cli_surface.py::test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices -q`

The final combined verification passed 65 tests.
