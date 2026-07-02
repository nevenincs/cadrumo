---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S21'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Counterpart 347/349 correctness gate follow-up

## Scope

- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`

## Description

- Add an M349 correctness gate in `src/aeat/application/aggregation/tests/test_per_modelo_service.py` comparing `CounterpartAggregationSourceResolver.resolve(...).binding_values` to values projected from the prior `aggregate_counterpart_349` output through the live M349 registry snapshot.
- Use a real mixed fixture: one collectible intra-community delivery, one payable intra-community service acquisition, and one domestic M347 control observation that must not enter the M349 resolution.
- Keep the oracle path independent of the resolver call: `aggregate_counterpart_349` produces the expected aggregation, `_registry_observations_from_counterpart_aggregation` adapts that aggregate to registry facts, `resolve_counterpart_binding_values` applies the live registry, and `_m349_declarante_summary_union` applies the existing payable-summary mirror fold.
- Extend the local `_counterpart_obs` test helper with explicit `source_id` and `name` parameters so mixed fixtures do not share source object identifiers.

## Outcome

- M349 correctness evidence landed: the per-modelo service aggregation equals the prior `aggregate_counterpart_349` output, and the counterpart mesh resolver emits exactly the same M349 binding values after live-registry projection.
- P03.S21 remains unchecked. The M347 half cannot be completed honestly at HEAD because Modelo 347 has no declared counterpart-source registry bindings; the resolver's activation path is `_counterpart_sources_for_revision`, so the current M347 snapshot resolves empty before it can compare against a non-empty aggregate.
- Formal blocker: `DFR-D9-P03-S21-M347-COUNTERPART-SOURCE-MODELLING`. Completing the 347 half requires either committed M347 counterpart-source registry modelling or a coordinator-approved resolver activation change. Both are outside this step's test-only scope and the program freeze forbids ad hoc resolver convention changes.
- Verification passed:
  - `uv run --no-sync ruff check src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync python -m py_compile src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py::test_counterpart_m349_mesh_resolution_matches_prior_aggregate_exactly src/aeat/application/aggregation/tests/test_per_modelo_service.py::test_service_routes_counterpart_modelos_and_preserves_threshold_semantics src/aeat/application/aggregation/tests/test_counterpart.py::TestCounterpartSourceResolver::test_resolver_materialises_m349_values_from_existing_aggregator`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py src/aeat/application/aggregation/tests/test_counterpart.py src/aeat/application/aggregation/tests/test_counterpart_347_cross_cohort_merge.py`

## Notes

- No P03.S21 plan check was run. This record is evidence plus formal deferral inventory, not closure.
- No registry, resolver-enrollment, or `_calculation_actions.py` edit was made.
