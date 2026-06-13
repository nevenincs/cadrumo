---
step_id: S230
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S230

## Outcome

Created `src/aeat/application/storage/calc_sheets/test_records.py` with three real-behavior tests:

- `test_utc_now_alias_is_the_canonical_clock` — `_utc_now is _now` identity check.
- `test_utc_now_returns_utc_aware_datetime` — confirms UTC-aware result.
- `test_utc_now_advances_monotonically` — two successive calls must not go backward.

## Test result

3 passed.

## Files touched

- `src/aeat/application/storage/calc_sheets/test_records.py` — new file
