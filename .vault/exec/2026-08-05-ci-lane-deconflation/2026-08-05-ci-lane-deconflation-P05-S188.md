---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0dd703dd3c9003bdda7383946358669f4b36c0dec3dfbf98c8c5dee9456f2391'
step_id: 'S188'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in ledger_bindings.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/ledger_bindings.py`

## Changes

- `M` `dev/registry/analysis/load_census_classification.py`
- `M` `src/cadrumo/application/aggregation/_iva_ledger.py`
- `M` `src/cadrumo/application/aggregation/_iva_transaction.py`
- `M` `src/cadrumo/application/aggregation/_m303_arrivals.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva_refusal.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_renta_expenses.py`
- `M` `src/cadrumo/application/aggregation/_oss_ioss.py`
- `M` `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`
- `M` `src/cadrumo/application/aggregation/tests/test_intracom_export.py`
- `M` `src/cadrumo/application/aggregation/tests/test_intracom_identification_not_establishment.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_declared_category_survives.py`
- `M` `src/cadrumo/application/aggregation/tests/test_iva_cash_accounting.py`
- `M` `src/cadrumo/application/aggregation/tests/test_iva_ledger.py`
- `M` `src/cadrumo/application/aggregation/tests/test_m303_arrivals.py`
- `M` `src/cadrumo/application/aggregation/tests/test_m303_transitional_rate_rung_allocation.py`
- `M` `src/cadrumo/application/aggregation/tests/test_modelo_390_rate_box_ledger_reachability.py`
- `M` `src/cadrumo/application/aggregation/tests/test_non_arising_category_side_is_refused.py`
- `M` `src/cadrumo/application/aggregation/tests/test_oss_ioss.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_income_actividad_contract.py`
- `M` `src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py`
- `M` `src/cadrumo/application/aggregation/tests/test_structurally_unroutable_iva_base_categories.py`
- `M` `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- `M` `src/cadrumo/application/aggregation/tests/test_unrouted_iva_quantity_screen.py`
- `M` `src/cadrumo/application/aggregation/tests/test_zero_cuota_category_carrying_a_rate_is_refused.py`
- `M` `src/cadrumo/application/aggregation/tests/test_zero_rated_row_carrying_cuota_is_refused.py`
- `M` `src/cadrumo/application/calculations/_prorrata_regularizacion.py`
- `M` `src/cadrumo/application/calculations/tests/test_binding_prefill.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_322_grupo_individual_continuity.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py`
- `M` `src/cadrumo/application/calculations/tests/test_prorrata_art104_tres_exclusion_oracle.py`
- `M` `src/cadrumo/application/calculations/tests/test_prorrata_regularizacion.py`
- `M` `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`
- `M` `src/cadrumo/application/registry/tests/test_namespace_is_not_a_registration_seam.py`
- `M` `src/cadrumo/domain/bienes_inversion/tests/test_record.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_binding_selector_support.py`
- `D` `src/cadrumo/domain/calculations/registry/ledger_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_oss_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_estimacion_directa_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_renta_gastos_pago_fraccionado_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/rate_box_partition.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/_ledger_iva_aggregation_support.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_reachability_probe.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_iva_rate_value_selector.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_expense_chain_aeat_local_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_aeat_exempt_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_exempt.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_rated.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_exports_recargo.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_reverse_charge.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_oss_aggregation_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_quantity_screen_partition.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_renta_gastos_estimacion_directa_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_renta_gastos_pago_fraccionado_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_renta_income_binding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m303_2024_regimen_general_manual_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m322_2024_grupo_entidades_manual_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m353_2024_grupo_entidades_manual_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m390_2024_annual_manual_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_aic_box_10_base_projection.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_differentiated_deduction_endpoints.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_transitional_rate_percent.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_309_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_322_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_369_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_aic_isp_routing_split.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_base_imponible_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_layer.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_reachability.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_recargo_rate_box_layer.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_volumen_operaciones.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_prorrata_porcentaje_rounding_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_prorrata_porcentaje_zero_volume_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_public_api_boundaries.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_unrouted_renta_quantity_screen.py`
- `M` `src/cadrumo/domain/calculations/registry/validate_cross_domain_snapshot.py`
- `M` `src/cadrumo/domain/iva/invoice_classification.py`
- `M` `src/cadrumo/domain/iva/tests/test_invoice_classification.py`
- `M` `src/cadrumo/domain/renta/retenciones_routing_integrity.py`
- `M` `src/cadrumo/domain/renta/tests/test_first_slice_routing.py`

## Notes

Source provenance is `f8dbe09b92e108bdec0fbc5ae0a0009cf9ae7bb2`. It deletes the 2148-line `ledger_bindings.py` subject and splits it into six siblings with physical counts 18, 821, 284, 265, 282, and 537; 61 definitions retain one-to-one ownership. The direct Python-import scan reports zero stale imports. No plan, size baseline, or threshold changed.

Supplied checks passed: compileall, I001/Ruff check, 108 tests in 94.10s, and 127 tests in 101.76s. The global size audit names none of the six new modules among 60 legacy overages; it is not a global green size claim.

The formatter finding at `dev/registry/analysis/load_census.py:729` is non-S188 and excluded. No full-green format claim is made.
