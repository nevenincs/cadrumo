---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S05'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Add retenciones aggregation source resolver

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Verify `RetencionesAggregationSourceResolver` reads the retencion observation repository and selects the per-modelo aggregation primitive.
- Verify the resolver materialises registry binding values through `resolve_retenciones_aggregation_binding_values`.
- Verify M111, M115, M180, and M193 resolver coverage remains present in current tests.

## Outcome

Retrospective execution record for an already-checked step. The resolver is present in `src/aeat/application/aggregation/_modelo_bindings.py` and uses the dedicated retencion store rather than relation-prefill or ledger-side shortcuts.

Verification: `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` passed as part of the P03 retenciones verification with 14 focused tests, and `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/aeat/application/aggregation/tests/test_retenciones.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` passed with 33 tests.

## Notes

This record was created on 2026-06-30 to close the plan-evidence gap for a step that had already been checked.
