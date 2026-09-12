---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:23c34c5df342bf8bf3dffc9f4589b3eb31160af45a172a305a592f287b0fa241'
step_id: 'S02'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Convert every selector model into a provider member with a literal kind and embedded temporal member, and declare the closed BindingProvider discriminated union

## Scope

- `src/cadrumo/domain/calculations/registry/binding_provider.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- `src/cadrumo/domain/calculations/registry/*_bindings.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/binding_provider.py`
- `A` `src/cadrumo/domain/calculations/registry/profile_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/bienes_inversion_regularizacion_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/iva_compensation_annual_partition_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/prorrata_regularizacion_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_selector_shape.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_targets.py`
- `M` `src/cadrumo/domain/calculations/registry/_ledger_binding_resolution.py`
- `M` `src/cadrumo/domain/calculations/registry/counterpart_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/design_constant_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/irnr_ledger_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_oss_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_estimacion_directa_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_pago_fraccionado_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/manual_input_selector.py`
- `M` `src/cadrumo/domain/calculations/registry/profile_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/retenciones_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal.py`
- `M` `src/cadrumo/domain/user_profile/registry_contract.py`
- `M` `src/cadrumo/domain/iva_compensation/filed_derivation.py`
- `verify:` `uv run ruff check` + `uv run ruff format` on the changed registry modules -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/tests/test_binding_provider.py` -> `pass`

## Notes

- Four corpus files were rewritten in place by this Step outside its declared scope: `src/cadrumo/_data/registry/aeat/modelos/131/revisions/{2019-2023,2024,2025,2026}/bindings/*.toml` had their previous-filing `selector` mapping edited to carry a `temporal` table while retaining the legacy `source` key. The P04 converter treats a selector already carrying `temporal` as pass-through, so these files converge with the rest of the corpus on that pass.
