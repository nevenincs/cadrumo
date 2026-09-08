---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:abf6b828f34bd7e427157bbfdb896c588a00db6e81c1d7d5904e27250d4da02d'
step_id: 'S130'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production binding-source enrollment, deferred, and reserved metastate registries, deriving routable sources solely from executable calculation-route ownership and refusing every declared binding without a live resolver

## Scope

- `calculation source mesh`
- `route ownership`
- `novel-source guard`
- `registry conformance`
- `ADR amendments`
- `and tests`

## Changes

- `M` `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`
- `M` `.vault/adr/2026-06-26-binding-resolver-contract-unification-adr.md`
- `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/revision.toml`
- `M` `src/cadrumo/application/aggregation/__init__.py`
- `M` `src/cadrumo/application/aggregation/_source_mesh.py`
- `D` `src/cadrumo/application/aggregation/tests/test_source_kind_enrollment_status.py`
- `M` `src/cadrumo/application/calculations/tests/test_grouping_dispatch_coverage.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `M` `src/cadrumo/application/modelo/calculation_source_policy.py`
- `D` `src/cadrumo/application/modelo/tests/test_binding_source_kind_mesh_parity.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_route.py`
- `D` `src/cadrumo/application/modelo/tests/test_deferred_detalle_source_advisories.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- `A` `src/cadrumo/application/modelo/tests/test_unrouted_source_refusal.py`
- `M` `src/cadrumo/core/aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_build_validation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_coverage_breadth.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_selector_shape.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py`
- `verify:` `uv run ruff check <S130 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 route, source-refusal, grouping, selector, validator, taxonomy, and breadth tests` -> `pass`
- `verify:` `uv run pytest -q -n0 src/cadrumo/application/modelo/tests/test_source_boundary_and_enrollment.py` -> `pass`
- `verify:` `rg exact retired disposition symbols across src/dev` -> `pass`

## Notes

The live zero-target route gate now fails on four mechanically derived source kinds across 21 bindings: `donativo_donor`, `gasto193_contributor`, `refund_operation`, and `related_party_operation`. Runtime detector-teeth tests prove every affected revision is refused with its exact current gap set. These findings remain open for executable resolver work; no development classification absorbs them.
