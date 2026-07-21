---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
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

## Current worktree follow-up check (2026-07-04)

- Non-authored WIP now exists for the M347 counterpart-source modelling follow-up:
  `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/bindings/0001-counterpart-summary.toml`,
  a construct reference in `constructs/0001-informative.toml`, and
  `src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py`.
- The WIP's domain-level registry-binding proof passes:
  `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py`
  (`2 passed`).
- The P03.S21 service-level proof remains blocked in the current shared worktree:
  `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_per_modelo_service.py::test_counterpart_m347_mesh_resolution_matches_prior_aggregate_exactly`
  fails before reaching the 347 assertion because non-authored untracked Modelo 145
  scaffolding invalidates registry authority (`revision must declare official workbook
  parity coverage`; `revision must declare at least one casilla`).
- P03.S21 remains unchecked until the 347 modelling is landed/owned and the service
  proof can run against a valid registry authority.

## Retry check (2026-07-04, observed at `f4ed27f35a`)

- Authoritative plan status remains open at `P03.S21`: `17/21` complete,
  `exec_missing_ids=[]`.
- Current focused counterpart service run remains red:
  `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart"`
  wrote full output to
  `C:\Users\hello\AppData\Local\Temp\aeat-d9-retry-counterpart-20260704.log`
  and exited `1` (`1 failed`, `2 passed`, `21 deselected`).
- The failing M349 proof still stops at registry authority load because the non-authored
  untracked Modelo 145 scaffold lacks official workbook parity coverage and any casilla.
- The current non-authored `test_per_modelo_service.py` WIP also weakens the M347 service check
  to `test_counterpart_m347_service_does_not_claim_invoice_owned_registry_bindings`; that checks
  non-claim behavior for invoice-owned bindings, not the plan row's exact equality between
  live-mesh resolution and the prior `aggregate_counterpart_347` output.
- No P03.S21 plan check was run.
