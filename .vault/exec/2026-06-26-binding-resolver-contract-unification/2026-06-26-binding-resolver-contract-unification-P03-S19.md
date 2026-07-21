---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Prove the retenciones collapse is behaviour-preserving by asserting the single mesh RetencionesAggregationSourceResolver reproduces the prior per-modelo-service aggregation value exactly against a 111/115/123/180/190/193 fixture, with the landed perceptor-count result unchanged and no casilla value shift

## Scope

- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`

## Description

Add a behaviour-preservation gate proving the S13 retenciones double-path collapse routes each modelo to the same core it did before, in `test_per_modelo_service.py`.

- Import the six retenciones aggregation cores and the mesh resolver into the test module.
- Add a mixed-scheme fixture carrying one observation per scheme family (work income, urban rental, capital interest) with distinct perceptor NIFs, so each modelo's scheme catalogue selects a distinct non-empty subset and a mis-wired dispatch would select the wrong subset.
- Add a parametrised gate over 111/115/123/180/190/193 asserting the canonical `RetencionesAggregationSourceResolver.aggregate` entry point AND the delegating `aggregate_per_modelo` service both reproduce the prior standalone core output exactly, deriving expected values from the pre-existing cores (the independent oracle), never from a hand-computed formula.
- Add an anti-tautology cross-wiring gate asserting the three quarterly modelos select disjoint scheme families and produce three distinct total_retencion values, so the equality-to-oracle assertions cannot be trivially satisfied.
- Add a landed-perceptor-count gate over two distinct-NIF urban observations asserting the annual 180 path still counts two distinct perceptors through the shared entry point.

## Outcome

The gate is green (23 passing in the file, 71 across the retenciones/service/resolver suites) and proven to bite: temporarily mis-wiring the 180 dispatch entry to the 111 core failed both the parametrised 180 oracle assertion (urban-scheme total 380.00 collapsing to 0 under the work-income filter) and the perceptor-count gate, and additionally tripped the `PerModeloAggregationResult` envelope-modelo-mismatch validator; reverting restored green. The landed RET-1 distinct-NIF perceptor-count result is unchanged and no casilla value shifts, satisfying `no-tautological-calculation-tests` (expectations derive from the pre-existing cores) and the plan's correctness-gate requirement for the collapse.

## Notes

The gate exercises the aggregation-value contract directly. The calculate-path binding-materialisation for the binding-declaring modelos remains covered by the existing `test_retenciones_aggregation_resolver.py` resolve gate, which stays green under the collapse.
