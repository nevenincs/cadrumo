---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:e7d4cfa0bf919d93c299d5a6f4ba1e5d965b6a399193799ef3868cbe19f424a2'
step_id: 'S17'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Migrate registry and application test modules that still construct legacy source/selector bindings or assert the deleted selector projection to the provider shape

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/application/**/tests/`
- `dev/registry/tests/`

## Changes

- `M` `dev/registry/tests/test_casilla_field_kind_enrollment.py`
- `M` `dev/registry/tests/test_formula_operand_casilla_refs.py`
- `M` `dev/registry/tests/test_ledger_renta_income_binding.py`
- `M` `dev/registry/tests/test_referential_integrity_part1.py`
- `M` `dev/registry/tests/test_referential_integrity_part3.py`
- `M` `dev/registry/tests/test_resolved_export_surface.py`
- `M` `dev/registry/tests/test_schema_hygiene.py`
- `M` `src/cadrumo/application/aggregation/tests/test_foreign_assets.py`
- `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `M` `src/cadrumo/application/aggregation/tests/test_iva_ledger.py`
- `M` `src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_income_actividad_contract.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `M` `src/cadrumo/application/aggregation/tests/test_retenciones_empty_store_advisory_guard.py`
- `M` `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- `M` `src/cadrumo/application/aggregation/tests/test_withholding_source_resolver.py`
- `M` `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime.py`
- `M` `src/cadrumo/application/modelo/tests/test_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_boolean_binding_decimal_error.py`
- `M` `src/cadrumo/application/modelo/tests/test_inventory_source_ownership.py`
- `M` `src/cadrumo/application/modelo/tests/test_rate_box_coverage_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_collect_row_sets.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_bindings_previous_filing.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_boolean_binding_encoding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_cross_modelo_carry_taxonomy.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_foreign_asset_binding_row_field.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_formula_operand_casilla_refs.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_inventory_selector.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_iva_rate_value_selector.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_manual_input_record_field_selector.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_previous_filing_binding_source_casilla_ids.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_profile_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_rate_box_partition.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_withholding_percepcion_count.py`
- `verify:` `uv run --no-sync ruff check <38 files>` -> `pass`
- `verify:` `uv run --no-sync ruff format --check <38 files>` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_casilla_field_kind_enrollment.py dev/registry/tests/test_resolved_export_surface.py dev/registry/tests/test_formula_operand_casilla_refs.py -n 0` -> `pass`

## Notes

The bundled authority artifact is stale, so the session-scoped autouse fixture in
`src/cadrumo/conftest.py` fails every test under `src/cadrumo/`. Those modules were
verified by direct execution of their test functions outside pytest; fixture-backed and
corpus-backed cases in them remain unverified until the artifact is rebuilt.

Two modules were left on the legacy shape because they read
`selector_model_for_source` and the `selector.*` manifest roots, production surfaces
outside this Step's scope:
`src/cadrumo/domain/calculations/registry/tests/test_filing_grade_binding_resolution.py`
and `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`.
