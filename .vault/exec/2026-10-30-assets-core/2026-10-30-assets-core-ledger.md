---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:da418a595e1e04302f02cc3ac3bb47258236bfa14ccfa32ee88c2ffc61e7130b'
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
- `S09` `M` `src/cadrumo/domain/modelos/calculation_revision_sources.py`
- `S09` `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `S09` `M` `src/cadrumo/application/aggregation/ledger_membership.py`
- `S09` `M` `src/cadrumo/application/modelo/_ledger_drift_gate.py`
- `S09` `M` `src/cadrumo/application/modelo/verification_gate_findings.py`
- `S09` `A` `src/cadrumo/application/modelo/activity_asset_claim_consumers.py`
- `S09` `A` `src/cadrumo/application/modelo/tests/test_ledger_drift_gate_activity_assets.py`
- `S09` `A` `dev/acceptance/assets/acquisition_seed.py`
- `S09` `verify:` `pytest test_ledger_drift_gate_activity_assets.py` -> `pass`
- `S09` `verify:` `pytest dev/acceptance/assets/tests` -> `pass`
- `S09` `verify:` `lint-imports` -> `pass`
- `S09` `by:` `vaultspec-standard-executor`
- `S07` `M` `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/application/aggregation/_shared_issue_reasons.py`
- `S07` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S07` `M` `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`
- `S07` `M` `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py`
- `S07` `M` `src/cadrumo/application/aggregation/renta_gasto_ledger.py`
- `S07` `M` `src/cadrumo/application/aggregation/renta_ledger_models.py`
- `S07` `M` `src/cadrumo/application/aggregation/tests/test_modelo_bindings_actividad_assets.py`
- `S07` `M` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`
- `S07` `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `S07` `M` `src/cadrumo/application/ledger/ratios.py`
- `S07` `M` `src/cadrumo/application/ledger/tests/test_ratios_censo_override.py`
- `S07` `M` `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_estimacion_directa_bindings.py`
- `S07` `M` `src/cadrumo/domain/categories/proportionality.py`
- `S07` `M` `src/cadrumo/domain/categories/proportionality_catalogue.py`
- `S07` `M` `src/cadrumo/domain/categories/registry.py`
- `S07` `M` `src/cadrumo/domain/categories/spending_category_catalogue.py`
- `S07` `M` `src/cadrumo/domain/categories/tests/test_registry.py`
- `S07` `M` `src/cadrumo/domain/renta/ledger_expenses.py`
- `S07` `M` `src/cadrumo/domain/renta/tests/test_ledger_expenses.py`
- `S07` `M` `src/cadrumo/domain/usage_ratios/service.py`
- `S07` `M` `src/cadrumo/domain/usage_ratios/tests/test_censo_derivation.py`
- `S07` `M` `src/cadrumo/domain/usage_ratios/tests/test_model.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_usage_ratios_censo_refuse_load.py`
- `S07` `M` `src/cadrumo/adapters/persistence/tests/test_usage_ratio_resolution.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_ratios_verbs.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/registered_executor_outcome_assertions.py`
- `S07` `M` `src/cadrumo/locales/en/common.yml`
- `S07` `M` `src/cadrumo/locales/es/common.yml`
- `S07` `M` `src/cadrumo/locales/ca/common.yml`
- `S07` `M` `src/cadrumo/locales/hu/common.yml`
- `S07` `verify:` `dev.registry.conformance integrity` -> `pass`
- `S07` `verify:` `pytest amortizable category and asset authority tests` -> `pass`

## Notes

- `S05` `operation_dtos.py` field removal lands with the S06 commit because the file shared another agent's edits.
- `S08` check-import-boundaries failed on another session's uncommitted core storage edits, in test-scoped code; rerun at review.
- `S08` Filing handoff `project_m130` still reads claims and accrual can run past the useful period; both moved to S12.
- `S06` Locale keys and three shared test files stayed uncommitted because they hold other sessions' hunks; installed journeys moved to S09; runtime-host and installed acceptance runs not repeated after collection recovered.
- `S04` 2 failures in `test_activity_asset_schedule_authority_resolution` raise from the history.py basis recheck, outside this Step, reported to the owner
- `S09` Commit 93b91e4bf2 swept S12 hunks in `modelo_bindings_actividad_assets.py` and `test_modelo_source_mesh_ledger.py.` Step stays open: five resolver-backed tests have not run, blocked on publishing the S07 authority.
- `S09` Open for review: `stale_filed_revisions` checks the ledger only, not the register; `export_journey` Modelo 130 control totals may need updating; installed journeys not run.
