---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:2ead11c15a76faeee822a53d88a4efa8ad3d3dc16fb89baf9af82b198f8806a7'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# `binding-schema` `P01` summary

## Changes

- A `dev/registry/compiler/validate_bindings.py`
- A `dev/registry/tests/test_validate_bindings.py`
- A `src/cadrumo/domain/calculations/registry/bienes_inversion_regularizacion_bindings.py`
- A `src/cadrumo/domain/calculations/registry/binding_provider.py`
- A `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- A `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- A `src/cadrumo/domain/calculations/registry/binding_terminal_origin.py`
- A `src/cadrumo/domain/calculations/registry/binding_value_contract.py`
- A `src/cadrumo/domain/calculations/registry/identifier_evolutions.py`
- A `src/cadrumo/domain/calculations/registry/iva_compensation_annual_partition_bindings.py`
- A `src/cadrumo/domain/calculations/registry/profile_bindings.py`
- A `src/cadrumo/domain/calculations/registry/prorrata_regularizacion_bindings.py`
- A `src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_provider.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_origin.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_value_contract.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_identifier_evolutions.py`
- D `src/cadrumo/domain/calculations/registry/tests/test_selector_shape.py`
- M (rename `DataBindingDefinition` -> `BindingDefinition`) 131 modules under `src/cadrumo/` and `dev/`
- M `dev/registry/compiler/_compiled_cache.py`
- M `dev/registry/compiler/_validate_revision_sections.py`
- M `dev/registry/compiler/loader_grammar.py`
- M `dev/registry/conformance/schema_family_support.py`
- M `dev/registry/conformance/tests/test_catalogue_verification_coverage.py`
- M `src/cadrumo/application/modelo/calculation_route.py`
- M `src/cadrumo/domain/calculations/registry/_ledger_binding_resolution.py`
- M `src/cadrumo/domain/calculations/registry/binding_aggregation.py`
- M `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- M `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- M `src/cadrumo/domain/calculations/registry/binding_targets.py`
- M `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- M `src/cadrumo/domain/calculations/registry/bindings.py`
- M `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- M `src/cadrumo/domain/calculations/registry/counterpart_bindings.py`
- M `src/cadrumo/domain/calculations/registry/design_constant_bindings.py`
- M `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- M `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- M `src/cadrumo/domain/calculations/registry/formula_initial_values.py`
- M `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- M `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- M `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- M `src/cadrumo/domain/calculations/registry/irnr_ledger_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_oss_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_estimacion_directa_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_pago_fraccionado_bindings.py`
- M `src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py`
- M `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py`
- M `src/cadrumo/domain/calculations/registry/manual_input_selector.py`
- M `src/cadrumo/domain/calculations/registry/profile_grounding.py`
- M `src/cadrumo/domain/calculations/registry/queries.py`
- M `src/cadrumo/domain/calculations/registry/reference_sections.py`
- M `src/cadrumo/domain/calculations/registry/relations.py`
- M `src/cadrumo/domain/calculations/registry/retenciones_bindings.py`
- M `src/cadrumo/domain/calculations/registry/schema.py`
- M `src/cadrumo/domain/calculations/registry/schema_base.py`
- M `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- M `src/cadrumo/domain/calculations/registry/snapshot.py`
- M `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal.py`
- M `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- M `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- M `src/cadrumo/domain/iva_compensation/filed_derivation.py`
- M `src/cadrumo/domain/user_profile/registry_contract.py`
