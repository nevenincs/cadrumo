---
tags:
  - '#exec'
  - '#retenciones-perceptor-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S03'
related:
  - "[[2026-06-24-retenciones-perceptor-count-plan]]"
---

# Verify retencion observation store roundtrip

## Scope

- `src/aeat/application/aggregation/tests`

## Description

- Verify strict save-load equality coverage for the encrypted retencion observation repository.
- Verify aggregation primitive tests cover distinct perceptor counting, per-scheme filtering, ordering stability, and non-default populated rows.
- Keep the record retrospective because the implementation and tests were already present before this checkpoint.

## Outcome

The P01 store behavior is covered by current real-behavior tests. The test surface imports the production repository, production observation model, and production aggregation primitives directly.

Verification: `uv run --no-sync pytest -q --tb=short src/aeat/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/aeat/application/aggregation/tests/test_retenciones.py src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` passed with 33 tests.

## Notes

No skipped or xfailed coverage was used for this closure record.
