---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:08282a8090eb1a785a84e9f2eb705bd5433b5cba8e94826dcd4e67a83acada19'
step_id: 'S13'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Collapse the retenciones double-path so the per-modelo service retenciones branch delegates to the same mesh RetencionesAggregationSourceResolver, retiring the duplicate retenciones service result type without changing the landed perceptor-count result

## Scope

- `src/aeat/application/aggregation/_service.py`

## Description

Collapse the two divergent retenciones aggregation dispatch tables onto ONE canonical mesh-resolver entry point so the calculate mesh and the per-modelo aggregation service cannot drift.

- Promote the mesh resolver's private modelo-to-aggregator map in `_modelo_bindings.py` to the single canonical retenciones dispatch covering every retenciones modelo (111, 115, 123, 180, 190, 193), rewriting its docstring to state it is shared by both the calculate mesh and the pull/service surface, and that the calculate path is scoped to the binding-declaring modelos by the resolver binding-guard rather than by table membership.
- Add the imports of the 123 and 190 cores plus the `RetencionesAggregation` and `RetencionObservation` types to `_modelo_bindings.py`.
- Add a canonical `RetencionesAggregationSourceResolver.aggregate` staticmethod that dispatches an observation set through the shared table and returns a `RetencionesAggregation`; route the resolver's own `resolve` calculate path through it, and change the resolver guard from a table `.get` to an explicit membership check so the defensive empty-resolution branch is unchanged.
- Delete the per-modelo service's local six-entry `dispatch` literal in `_service.py::_aggregate_retenciones` and delegate to `RetencionesAggregationSourceResolver.aggregate`, importing the resolver intra-package and dropping the now-unused per-core imports (keeping `RetencionesAggregation` and `RetencionObservation`).

## Outcome

The per-modelo service retenciones branch and the live calculate mesh now produce retenciones aggregation through one shared dispatch, honouring `one-aggregation-path-pull-equals-calculate` and `composition-service-no-parallel-write-path` (no re-implemented aggregation path). Calculate-path behaviour is unchanged: only 111/115/180/193 declare the `retenciones_aggregation` binding, and the resolver binding-guard scopes `resolve` to those before any aggregator lookup, so widening the shared table to include the pull-only 123/190 cannot resolve a new calculate value. Focused gates green: the per-modelo service, service, retenciones, retenciones-aggregation-resolver, and 193 totals-parity suites (71 passing), the mesh parity and pull-vs-calculate casilla parity gates (12 passing), ruff clean, and `pytest --collect-only -q` clean across the aggregation, modelo, and calculations trees with zero collection errors.

## Notes

No peer WIP on the three touched files at HEAD. During the anti-tautology mutation probe (temporarily mis-wiring the 180 dispatch to the 111 core to confirm the S19 gate bites), ruff auto-stripped the then-unused `aggregate_retenciones_180` import; the import was restored on revert and re-linted clean. The counterpart 347/349 and foreign-assets 720 branches of the service are untouched and remain shape-C CLI-reachable, deferred to follow-up task #36 per the plan scope refinement.
