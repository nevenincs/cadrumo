---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S05'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Clean stale threshold-axis obligation-layer documentation so the application gate is described as block-based

## Scope

- `src/aeat/core/_foreign_asset_obligation.py`

## Description

- Updated the module documentation to point to the application aggregation gate as per-obligation-block rather than per-class.
- Preserved the existing obligation-group map and threshold models.

## Outcome

- The core obligation semantic layer and application aggregation documentation now agree that the legally load-bearing axis is the obligation block.
- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py --tb=short` reported 14 passed.

## Notes

- No core threshold values or legal refs changed.
