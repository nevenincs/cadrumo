---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S01'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Define typed per-perceptor retencion observation record

## Scope

- `src/aeat/application/aggregation`

## Description

- Verify the current typed retenciones observation model in `src/aeat/application/aggregation/_retenciones.py`.
- Confirm the model carries source provenance, perceptor identity, scheme, taxable base, retention amount, and accrual date as strict pydantic fields.
- Confirm the aggregation payload exposes stable per-perceptor rollups and total scalar facts consumed by registry bindings.

## Outcome

Retrospective execution record for an already-checked step. Current code contains the dedicated typed `RetencionObservation` and `RetencionesAggregation` primitives required by P01.

Verification: `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/aeat/application/aggregation/tests/test_retenciones.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` passed with 33 tests.

## Notes

This record was created on 2026-06-30 to close the plan-evidence gap for a step that had already been checked.
