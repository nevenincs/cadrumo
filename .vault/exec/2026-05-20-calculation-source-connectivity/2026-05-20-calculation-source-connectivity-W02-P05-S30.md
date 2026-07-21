---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S30'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Enroll retenciones aggregation through repository backed source resolution

## Scope

- `src/aeat/application/aggregation/_retenciones.py`

## Description

Verified the step is already implemented at HEAD by prior source-mesh work; this record closes it against real gate evidence rather than re-implementing.

- Confirmed `RetencionesAggregationSourceResolver` is enrolled in the live `merge_source_resolutions` mesh tuple on the calculate path, reading the dedicated per-perceptor retención observations store through its repository rather than a synthetic in-memory source.
- Confirmed the resolver materialises the retenciones family bindings from real persisted observations: Modelo 115 quarterly count and base, and Modelo 180 / 193 distinct perceptor-NIF counts, scheme-filtered where the binding declares a scheme.
- Confirmed an empty retenciones store on a declaring revision surfaces a no-silent advisory and still materialises an explicit zero rather than a silent blank, honouring the no-dormant-source-resolvers and no-silent-under-declaration rules.

## Outcome

Retenciones aggregation is enrolled through repository-backed source resolution on the live mesh. No production code change was required; the step was already satisfied at HEAD.

Gate evidence: `test_retenciones_aggregation_resolver.py` green (real-store distinct perceptor count, Modelo 115 count and base, Modelo 111 scheme-filtered bindings, empty-store fail-before-silent-zero); `test_retenciones_empty_store_advisory_guard.py` green; the reflective enrollment gate `test_source_resolver_enrollment.py` green.

## Notes

Closed as verified-at-HEAD. The resolver lives in `src/aeat/application/aggregation/_retenciones.py` and is enrolled from the mesh builder in `src/aeat/application/modelo/_calculation_actions.py`.
