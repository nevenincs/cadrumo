---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P09.S30'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P09.S30 - Extract previous-filing binding family

Plan: `.vault/plan/2026-06-04-repo-health-triage-plan.md`
Step: W03.P09.S30
Status: complete

## Change

- Added `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- Moved the previous-filing selector model, observation requirement model,
  requirement walker, direct resolver, period-offset helpers, and aggregation
  helper out of `_bindings.py`.
- Kept `_bindings.py` as the compatibility export surface for:
  - `RegistryModeloObservationRequirement`
  - `_PreviousModeloSelector`
  - `previous_filing_observation_requirements`
  - `resolve_previous_filing_binding_values`
- Preserved `RegistryModeloObservation` and `OracleModeloObservation` in
  `_bindings.py`, because they are shared observation envelopes across
  application and persistence surfaces, not previous-filing-only objects.

## Verification

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_bindings_previous_filing.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py`
  - Result: passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_selector_shape.py -q`
  - Result: 45 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py::test_modelo_130_resolves_previous_year_modelo_100_filed_casillas_into_binding -q`
  - Result: 2 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py::test_registry_filing_observation_preserves_observation_tuple src/aeat/domain/calculations/registry/test_cross_boundary_roundtrip.py::test_oracle_filing_observation_distinct_from_local_roundtrip -q`
  - Result: 2 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py -q`
  - Result: 42 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
  - Result: 3 passed.

## Shared-tree note

The broader command `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py -q` had one failure in `test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados`: the current shared tree exposes two extra M200 self-relations in that assertion. That is not caused by this extraction and is not in the touched file set.

## Reviewability

- `_bindings.py`: 3061 lines before extraction, 2708 after extraction.
- `_bindings_previous_filing.py`: 296 lines, below the default new-validator-module reviewability ceiling.
