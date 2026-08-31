---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:38ba39a2235bdc43f365c4c3a732089d18a7d9464b086a30b7f30d19021c3aab'
step_id: 'S131'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _renta_income_ledger.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py`

## Changes

- `M` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `A` `src/cadrumo/application/aggregation/_renta_income_evidence.py`
- `M` `src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py`
- `M` `src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py`
- `M` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S131.md`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aggregation/_renta_income_ledger.py src/cadrumo/application/aggregation/_renta_income_evidence.py src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py` -> `pass` (28 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_inferred_retencion_rate_advisory.py src/cadrumo/application/aggregation/tests/test_renta_income_aggregation.py` -> `pass` (33 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_agricola_receipt_reaches_casilla_05 src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_every_code_in_the_registry_selector_contributes src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_non_agrarian_activity_stays_out_of_the_agrarian_box` -> `pass` (3 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_undeclared_activity_contributes_nothing src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_capital_subsidy_is_excluded_but_a_current_one_is_not src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_indemnity_is_excluded src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_undeclared_concept_is_included src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_mixed_catalogue_sums_only_the_qualifying_rows` -> `pass` (5 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_renta_income_observation_preserves_es_source_jurisdiction src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_renta_income_aggregation_mixes_es_and_foreign_source src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_annual_income_sums_full_ejercicio_into_casilla_0171 src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_annual_income_rejects_non_annual_period` -> `pass` (4 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_repository_backed_m100_aggregation_reports_out_of_period_catalogue_transactions src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_repository_backed_m100_aggregation_partition_matches_full_scan` -> `pass` (2 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_revision_binds_0171_to_income_source_and_resolves` -> `pass` (1 passed)
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/application/aggregation/tests/test_undeclared_activity_advisory.py` -> `pass` (10 passed)
- `verify:` `uv run --no-sync python -c "from cadrumo.tests import measure_module_lines; modules = measure_module_lines(); assert modules['src/cadrumo/application/aggregation/_renta_income_ledger.py'] <= 1250; print('ledger lines=' + str(modules['src/cadrumo/application/aggregation/_renta_income_ledger.py']))"` -> `pass` (1057 lines)

## Notes

- `uv run --no-sync python dev/audit/size_budget.py` -> exit 1 with 86 remaining findings owned by later P05 steps; `_renta_income_ledger.py` is absent from the verdict and no baseline was changed.
