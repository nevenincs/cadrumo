---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:94764042c67af2937dfd7f613c6f9b29d1cc904a85bea4a9be7720d19ea1e5ba'
step_id: 'S40'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enroll the inventory resolver and explicit source disposition

## Scope

- `src/cadrumo/application/aggregation/_source_mesh.py`

## Description

- Promote inventory from deferred to enrolled in the canonical calculation-route ownership catalogue.
- Export only the public inventory resolver through the aggregation facade.
- Preserve runtime repository construction and invocation for S41.
- Add route-derived enrollment, disposition, uniqueness, discovery, and missing-source parity tests.

## Outcome

Inventory now has one canonical mesh-stage owner, resolver identity `inventory`, and an enrolled route disposition. It is absent from the deferred set, publicly discoverable through the aggregation facade, and covered by the existing total-disjoint disposition partition. The live runtime does not yet construct or invoke the repository resolver; that orchestration remains explicitly assigned to S41.

The implementation updates no census status, registry bindings, caller-override policy, or calculation persistence. Allocation-free no-binding behavior, value-free diagnostics, sealed source provenance, and retained conflict advisories remain owned by the S39 resolver.

Independent review reported zero findings. Fifty-eight focused tests passed and Ruff and scoped diff hygiene were clean.

## Notes

Grounding showed that `_source_mesh.py` owns deferred classification while `_calculation_route.py` owns canonical resolver-stage enrollment. The approved S40 scope expanded minimally to the route catalogue and aggregation facade; `_calculation_actions.py` remains untouched.

The type-check gate is not clean repository-wide: the shared tree currently reports 1,257 unrelated diagnostics, and a narrow invocation exposes pre-existing `_calculation_route.py` protocol and `ModeloCalculationRouteId` diagnostics. Review found no S40-specific type regression. This baseline was recorded rather than broadened into unrelated repair.
