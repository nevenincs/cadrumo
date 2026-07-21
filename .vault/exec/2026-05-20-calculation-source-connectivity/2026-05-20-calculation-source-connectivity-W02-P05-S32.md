---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test retenciones source observations are period and source kind filtered

## Scope

- `src/aeat/application/aggregation/test_source_mesh_retenciones.py`

## Description

Verified the required test coverage exists at HEAD; this record closes the test step against the realized coverage rather than adding a duplicate file.

- Confirmed `test_retenciones_aggregation_resolver.py` asserts retenciones source observations are period-filtered: the resolver materialises bindings for a `CalculationSourceContext` scoped to a specific filing year and period token (for example Modelo 115 for 2026 1T, Modelo 180/193 for 2024 0A) and excludes out-of-window observations.
- Confirmed the coverage asserts source-kind and scheme filtering: Modelo 111 scheme-filtered bindings materialise only from observations whose scheme matches the binding, and mixed-scheme stores route each observation to its correct binding.
- Confirmed the empty-store guard: a declaring revision with no matching observations fails before a silent zero and surfaces the period in the advisory context.

## Outcome

Retenciones source observations are proven to be period- and source-kind-filtered by the consolidated retenciones resolver test. No new test file was required; the plan's `test_source_mesh_retenciones.py` intent is satisfied by `test_retenciones_aggregation_resolver.py`.

Gate evidence: `test_retenciones_aggregation_resolver.py` green (period-scoped materialisation, scheme filtering, distinct perceptor count, empty-store fail-before-silent-zero); `test_retenciones_empty_store_advisory_guard.py` green.

## Notes

Closed as verified-at-HEAD. The plan named a standalone `test_source_mesh_retenciones.py`; the realized coverage lives in `src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` and the sibling empty-store advisory guard, co-located with the resolver per the tests-live-under-domain-tests-folders topology.
