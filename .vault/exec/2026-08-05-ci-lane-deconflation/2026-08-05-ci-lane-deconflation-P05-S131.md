---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5226843a01beb20c932f99d6d57a3ca59077fcc0d0cb2533d2ae9ff851d8b061'
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
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py src/cadrumo/application/aggregation/tests/test_income_withheld_derivation.py` -> `28 passed in 6.23s`; `PYTEST_EXIT=0`; raw collection `28`; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_inferred_retencion_rate_advisory.py src/cadrumo/application/aggregation/tests/test_renta_income_aggregation.py` -> `33 passed in 4.33s`; `PYTEST_EXIT=0`; raw collection `33`; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_agricola_receipt_reaches_casilla_05 src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_every_code_in_the_registry_selector_contributes src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_non_agrarian_activity_stays_out_of_the_agrarian_box` -> `3 passed in 2.14s`; `PYTEST_EXIT=0`; raw module collection `8`; explicit node selection `3`, with `5` out of this command and covered by the next M131 command; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_undeclared_activity_contributes_nothing src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_capital_subsidy_is_excluded_but_a_current_one_is_not src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_indemnity_is_excluded src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_an_undeclared_concept_is_included src/cadrumo/application/aggregation/tests/test_m131_volumen_agrario.py::test_a_mixed_catalogue_sums_only_the_qualifying_rows` -> `5 passed in 2.16s`; `PYTEST_EXIT=0`; raw module collection `8`; explicit complementary node selection `5`, with `3` in the preceding M131 command; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_renta_income_observation_preserves_es_source_jurisdiction src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_renta_income_aggregation_mixes_es_and_foreign_source src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_annual_income_sums_full_ejercicio_into_casilla_0171 src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_annual_income_rejects_non_annual_period` -> `4 passed in 1.91s`; `PYTEST_EXIT=0`; raw module collection `7`; explicit node selection `4`, with `3` out of this command and covered by the next two M100 commands; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_repository_backed_m100_aggregation_reports_out_of_period_catalogue_transactions src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_repository_backed_m100_aggregation_partition_matches_full_scan` -> `2 passed in 3.39s`; `PYTEST_EXIT=0`; raw module collection `7`; explicit node selection `2`, with `5` in the preceding/following M100 commands; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py::test_m100_revision_binds_0171_to_income_source_and_resolves` -> `1 passed in 31.81s`; `PYTEST_EXIT=0`; raw module collection `7`; explicit final node selection `1`, with `6` in the preceding M100 commands; deselected `0`
- `verify:` `uv run --no-sync pytest -o addopts= -n0 -q src/cadrumo/application/aggregation/tests/test_undeclared_activity_advisory.py` -> `10 passed in 30.97s`; `PYTEST_EXIT=0`; raw collection `10`; deselected `0`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests import measure_module_lines; modules = measure_module_lines(); assert modules['src/cadrumo/application/aggregation/_renta_income_ledger.py'] <= 1250; print('ledger lines=' + str(modules['src/cadrumo/application/aggregation/_renta_income_ledger.py']))"` -> `pass` (1057 lines)

## Notes

- The eight raw-addopts executions cover 86 tests: full collections of 28, 33, 8, 7 and 10, with only the M131 (3 + 5) and M100 (4 + 2 + 1) files deliberately split into exhaustive explicit node groups for deterministic capture. No marker filter or runner deselection applied.
- `uv run --no-sync python dev/audit/size_budget.py` -> exit 1 with 86 remaining findings owned by later P05 steps; `_renta_income_ledger.py` is absent from the verdict and no baseline was changed.
