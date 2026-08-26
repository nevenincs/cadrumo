---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:666666356945c8fc308bbeb41d862baa405134626cdb7ddf20cf4e2a7872c6e3'
step_id: 'S16'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove acquisition is never implicit and reconciliation persists only accepted decisions through public contracts

## Scope

- `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/ -q -m "unit or integration"` -> `pass` (21 passed)

## Notes

Found and fixed a real production defect while writing these proofs: CensalFieldReviewScreen's apply-all button called SelectionList.select/deselect with a loop index where the API requires the option's own value, so reverting to the suggested selection was a silent no-op. Fixed in sync_review.py (S15's file) and regression-tested here.
