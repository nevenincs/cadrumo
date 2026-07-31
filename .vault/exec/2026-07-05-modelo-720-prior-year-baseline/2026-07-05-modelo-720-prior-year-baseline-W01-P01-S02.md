---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:623f11a3bbee697e7759b8fdad455abf7835a1604ac65de235b69385a71f3d52'
step_id: 'S02'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Add real-behavior aggregation and per-modelo resolver gates for mixed security and insurance rows crossing the shared block floor

## Scope

- `src/aeat/application/aggregation/tests/test_foreign_assets.py`
- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`

## Description

- Added an aggregation test where `SECURITY` is 30000.00 EUR and `INSURANCE` is 25000.00 EUR, proving both classes become declarable through the shared 42-ter obligation block.
- Added an exact-boundary test where the shared block total is exactly 50000.00 EUR, proving equality does not cross the declaration floor.
- Added a per-modelo service and resolver test that projects both mixed rows through the live Modelo 720 registry row bindings and preserves provenance.

## Outcome

- The tests would fail under the old per-class gate because neither individual class exceeded 50000.00 EUR.
- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/aggregation/tests/test_per_modelo_service.py --tb=short` reported 48 passed.

## Notes

- No fakes, mocks, skips, or xfails were used.
