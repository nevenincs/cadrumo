---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7e0547d3fee931a4e59ea4327d292ea8a9d32c541b5409a709a3c6f10278c66f'
step_id: 'S130'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _modelo_bindings.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Changes

- `M` `src/cadrumo/application/aggregation/__init__.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `A` `src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py`
- `A` `src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva_refusal.py`
- `A` `src/cadrumo/application/aggregation/_modelo_bindings_renta_expenses.py`
- `A` `src/cadrumo/application/aggregation/_modelo_bindings_retenciones.py`
- `A` `src/cadrumo/application/aggregation/_modelo_bindings_support.py`
- `M` `src/cadrumo/application/aggregation/_service.py`
- `M` `src/cadrumo/application/modelo/_calculation_actions.py`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `M` `src/cadrumo/application/aggregation/tests/test_currency_conversion_pipeline_parity.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_and_bank_feeds_agree.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_category_counterparty_mismatch_is_reported.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_declared_category_survives.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_line_currency_refusal.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_screen_exempt_lines.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_screen_reports_storage_degradation.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_screen_routes_exempt_base.py`
- `M` `src/cadrumo/application/aggregation/tests/test_m390_invoice_reachability.py`
- `M` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`
- `M` `src/cadrumo/application/aggregation/tests/test_per_modelo_service.py`
- `M` `src/cadrumo/application/aggregation/tests/test_recargo_rate_advisory.py`
- `M` `src/cadrumo/application/aggregation/tests/test_retenciones_aggregation_resolver.py`
- `M` `src/cadrumo/application/aggregation/tests/test_retenciones_empty_store_advisory_guard.py`
- `M` `src/cadrumo/application/aggregation/tests/test_supplier_side_reverse_charge_reaches_casilla_122.py`
- `M` `src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_invoice_declared_category_survives.py src/cadrumo/application/aggregation/tests/test_retenciones_aggregation_resolver.py src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py` -> `pass`

## Notes

- `dfdd054b32` captured the in-flight S130 source and consumer sweep before this executor could create its atomic close; this record and the residual policy-sibling/test-inventory diff complete the same approved S130 scope without reverting peer work.
- `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_invoice_declared_category_survives.py src/cadrumo/application/aggregation/tests/test_retenciones_aggregation_resolver.py src/cadrumo/application/aggregation/tests/test_terminal_preconditions.py` -> `20 passed in 38.99s`, exit `0`.
- `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_renta_ledger.py -k "renta_filing_aggregation_resolves_registry_bound_inputs or renta_filing_aggregation_loads_usage_ratios_for_mobile_phone_expenses"` -> `2 passed, 31 deselected in 4.53s`, exit `0`.
- `uv run --no-sync python -m dev.audit.size_budget` -> exit `1`: `_modelo_bindings.py` is no longer over budget (measures `1102`); its old `2456` pin is stale and is intentionally deferred to P05.S227. The remaining `63` module and `22` callable overages are other approved P05 owners.
