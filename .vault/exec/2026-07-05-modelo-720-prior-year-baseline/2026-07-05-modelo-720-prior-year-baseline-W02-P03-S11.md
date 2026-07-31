---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:3efc84dbbc1bb11c8bf4642bcf4e3259b905ef7e52dc5b801d8a7dab3d4fbdc9'
step_id: 'S11'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Add M720 row-projection tests proving real estate emits B and virtual currency cannot be emitted through Modelo 720

## Scope

- `src/aeat/application/aggregation/tests/test_foreign_assets.py`

## Description

- Added a live Modelo 720 row-projection test that aggregates declarable IIC and real-estate observations, resolves them through the registry row bindings, and proves the emitted row class codes are `I` and `B`.
- Added a fail-closed projection test where a declarable virtual-currency observation reaches row projection and raises instead of producing a Modelo 720 row.

## Outcome

- The row-binding path now proves real estate emits `B` and IIC emits `I` through the same registry resolver used by the production aggregation path.
- Virtual currency cannot be silently emitted through Modelo 720.

## Notes

- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py src/aeat/application/aggregation/tests/test_foreign_assets.py --tb=short` reported 42 passed.
- Broader phase verification passed with `src/aeat/application/aggregation/tests/test_per_modelo_service.py` included and reported 67 passed.
