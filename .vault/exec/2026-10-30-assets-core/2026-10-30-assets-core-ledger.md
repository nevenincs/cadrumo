---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:a1bc9bbc4fde7b5c8737496563934dbc016d3bdfc0112845ec57fd1a72b51a4e'
related:
  - "[[2026-10-30-assets-core-plan]]"
---

# `assets-core` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/renta/actividad_asset/schedule.py`
- `S01` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_lifecycle.py`
- `S01` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests` -> `pass`
- `S01` `verify:` `pytest src/cadrumo/application/actividad_asset/tests` -> `pass`
- `S01` `verify:` `ruff check` -> `pass`
- `S05` `M` `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `S05` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_claims.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/history.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/tests/test_history.py`
- `S05` `M` `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`
- `S05` `M` `src/cadrumo/application/actividad_asset/operation_dtos.py`
- `S05` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests` -> `pass`
- `S05` `verify:` `pytest src/cadrumo/application/actividad_asset/tests` -> `pass`
- `S05` `verify:` `pytest test_modelo_bindings_actividad_assets.py` -> `pass`
- `S05` `by:` `vaultspec-standard-executor`
- `S10` `A` `.vault/adr/2026-10-30-assets-core-disposal-adr.md`
- `S10` `M` `.vault/adr/2026-09-21-assets-core-lifecycle-contract-adr.md`
- `S08` `M` `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`
- `S08` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S08` `M` `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py`
- `S08` `M` `src/cadrumo/application/aggregation/renta_ledger.py`
- `S08` `M` `src/cadrumo/application/aggregation/renta_gasto_ledger.py`
- `S08` `M` `src/cadrumo/application/aggregation/source_diagnostic_reason.py`
- `S08` `M` `src/cadrumo/application/modelo/calculation_notes.py`
- `S08` `M` `src/cadrumo/application/modelo/calculation_bucket_actions.py`
- `S08` `M` `src/cadrumo/domain/modelos/calculation_revision_sources.py`
- `S08` `M` `src/cadrumo/adapters/persistence/profile/actividad_asset.py`
- `S08` `M` `native/desktop/frontend/src/shell/modeloContract.ts`
- `S08` `verify:` `pytest test_modelo_bindings_actividad_assets.py` -> `pass`
- `S08` `verify:` `pytest test_modelo_source_mesh_ledger.py` -> `pass`
- `S08` `verify:` `lint-imports` -> `pass`
- `S08` `verify:` `just check-import-boundaries` -> `fail`
- `S08` `by:` `vaultspec-high-executor`
- `S06` `M` `src/cadrumo/domain/renta/actividad_asset/lifecycle.py`
- `S06` `A` `src/cadrumo/application/actividad_asset/acquisition_ledger.py`
- `S06` `A` `src/cadrumo/application/actividad_asset/tests/ledger_support.py`
- `S06` `M` `src/cadrumo/application/actividad_asset/ports.py`
- `S06` `M` `src/cadrumo/application/actividad_asset/operations.py`
- `S06` `M` `src/cadrumo/application/actividad_asset/operation_dtos.py`
- `S06` `M` `src/cadrumo/entrypoints/actividad_asset_composition.py`
- `S06` `M` `native/desktop/frontend/src/components/ledger/setup/setupModel.ts`
- `S06` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests` -> `pass`
- `S06` `verify:` `pytest src/cadrumo/application/actividad_asset/tests` -> `pass`
- `S06` `by:` `vaultspec-standard-executor`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/parameters/0001-declarations.toml`
- `S04` `M` `dev/registry/tests/test_activity_asset_authority_across_supported_years.py`
- `S04` `A` `dev/registry/tests/test_amortization_tables_match_the_law.py`
- `S04` `verify:` `pytest dev/registry/tests/test_amortization_tables_match_the_law.py` -> `pass`
- `S04` `verify:` `pytest dev/registry/tests/test_activity_asset_authority_across_supported_years.py` -> `pass`

## Notes

- `S05` `operation_dtos.py` field removal lands with the S06 commit because the file shared another agent's edits.
- `S08` check-import-boundaries failed on another session's uncommitted core storage edits, in test-scoped code; rerun at review.
- `S08` Filing handoff `project_m130` still reads claims and accrual can run past the useful period; both moved to S12.
- `S06` Locale keys and three shared test files stayed uncommitted because they hold other sessions' hunks; installed journeys moved to S09; runtime-host and installed acceptance runs not repeated after collection recovered.
- `S04` 2 failures in `test_activity_asset_schedule_authority_resolution` raise from the history.py basis recheck, outside this Step, reported to the owner
