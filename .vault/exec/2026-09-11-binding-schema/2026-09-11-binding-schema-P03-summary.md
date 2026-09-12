---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:993ec259166af1e4910937643a0a19d553b61a1959474ef58946ac8a352b8aeb'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# `binding-schema` `P03` summary

## Changes

- M `dev/docs/casilla_reference.py`
- M `dev/registry/compiler/_validate_export_exemption.py`
- M `dev/registry/tests/test_casilla_field_kind_enrollment.py`
- M `dev/registry/tests/test_formula_operand_casilla_refs.py`
- M `dev/registry/tests/test_ledger_renta_income_binding.py`
- M `dev/registry/tests/test_referential_integrity_part1.py`
- M `dev/registry/tests/test_referential_integrity_part3.py`
- M `dev/registry/tests/test_resolved_export_surface.py`
- M `dev/registry/tests/test_schema_hygiene.py`
- M `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- M `src/cadrumo/application/aggregation/inventory.py`
- M `src/cadrumo/application/aggregation/iva_ledger.py`
- M `src/cadrumo/application/aggregation/modelo_bindings.py`
- M `src/cadrumo/application/aggregation/oss_ioss.py`
- M `src/cadrumo/application/aggregation/service.py`
- M `src/cadrumo/application/aggregation/tests/test_foreign_assets.py`
- M `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- M `src/cadrumo/application/aggregation/tests/test_iva_ledger.py`
- M `src/cadrumo/application/aggregation/tests/test_iva_ledger_candidates.py`
- M `src/cadrumo/application/aggregation/tests/test_renta_income_actividad_contract.py`
- M `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- M `src/cadrumo/application/aggregation/tests/test_retenciones_empty_store_advisory_guard.py`
- M `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- M `src/cadrumo/application/aggregation/tests/test_withholding_source_resolver.py`
- M `src/cadrumo/application/calculations/_per_grupo_member_keys.py`
- M `src/cadrumo/application/calculations/binding_prefill.py`
- M `src/cadrumo/application/calculations/foreign_asset_redeclaration.py`
- M `src/cadrumo/application/calculations/prorrata_regularizacion.py`
- M `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`
- M `src/cadrumo/application/filing/draft_construction.py`
- M `src/cadrumo/application/filing/runtime.py`
- M `src/cadrumo/application/filing/tests/test_runtime.py`
- M `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- M `src/cadrumo/application/modelo/_profile_export_binding.py`
- M `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- M `src/cadrumo/application/modelo/borrador_binding.py`
- M `src/cadrumo/application/modelo/profile_binding.py`
- M `src/cadrumo/application/modelo/tests/test_actions.py`
- M `src/cadrumo/application/modelo/tests/test_boolean_binding_decimal_error.py`
- M `src/cadrumo/application/modelo/tests/test_inventory_source_ownership.py`
- M `src/cadrumo/application/modelo/tests/test_rate_box_coverage_advisory.py`
- M `src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py`
- M `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- M `src/cadrumo/application/modelo/workspace_manifest.py`
- M `src/cadrumo/application/storage/calc_sheets/tests/test_collect_row_sets.py`
- M `src/cadrumo/domain/calculations/registry/queries.py`
- M `src/cadrumo/domain/calculations/registry/query_reports.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_bindings_previous_filing.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_boolean_binding_encoding.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_cross_modelo_carry_taxonomy.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_foreign_asset_binding_row_field.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_formula_operand_casilla_refs.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_inventory_selector.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_iva_rate_value_selector.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_manual_input_record_field_selector.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_previous_filing_binding_source_casilla_ids.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_profile_grounding.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_rate_box_partition.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_withholding_percepcion_count.py`
- M `src/cadrumo/domain/user_profile/registry_contract.py`
