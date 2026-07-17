---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Repair M720 declarability to aggregate present classes by regulatory obligation block before applying the strict declaration floor

## Scope

- `src/aeat/application/aggregation/_foreign_assets.py`

## Description

- Replaced the per-asset-class threshold total with a per-obligation-block total keyed by `foreign_asset_obligation_group`.
- Read the applicable threshold from `foreign_asset_declaration_threshold(group).initial_declaration_floor_eur` instead of importing the scalar threshold constant into the application gate.
- Preserved the existing rollup shape by `(source_kind, asset_class)` and changed only the declarability filter used by row projection and resolver selection.

## Outcome

- Mixed `SECURITY` and `INSURANCE` observations now cross the shared valores, derechos, seguros, and rentas block when their combined valuation is above 50000.00 EUR.
- The strict greater-than boundary is preserved.
- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/aggregation/tests/test_per_modelo_service.py --tb=short` and `uv run --no-sync ruff check` on touched Python files.

## Notes

- The separate class-code taxonomy defect remains open in Wave W02.
