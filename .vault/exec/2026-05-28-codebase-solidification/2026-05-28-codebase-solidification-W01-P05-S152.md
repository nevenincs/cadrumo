---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S152
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P05-S151]]"
---

# codebase-solidification W01.P05.S152 — real-behavior tests for `format_decimal`

## Outcome

Created `src/aeat/core/decimal/test_format.py` with 30 parametrized unit tests
covering all behavioral variants of `format_decimal`.

## Test coverage

- `normalize=False` (8 cases): positive, negative, zero, large, small, trailing zeros preserved
- `normalize=True` (9 cases): strip trailing zeros, integer result, large exponent
- None rejected by default (1 case): `TypeError` raised with message
- `none_value` policy (4 cases): None→custom string, non-None value unaffected
- `normalize=True` + `none_value="0"` combo (5 cases): mirrors `_projection.py` usage
- `_censo_live.py` caller pattern (3 cases): normalize then `.00` suffix logic

## pytest outcome

30/30 passed. Markers: `unit`, `domain_core`.

## Files created

- `src/aeat/core/decimal/test_format.py`
