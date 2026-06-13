---
step_id: S142
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P05.S142 — real-behavior test for `_now`

## Outcome

Created `src/aeat/core/time/test_clock.py` with four real-behavior tests:
`test_returns_utc_aware_datetime` (tzinfo is UTC), `test_result_is_recent`
(bounded by wall-clock before/after), `test_successive_calls_are_monotone`, and
`test_offset_is_zero`. No mocks, no skips, no xfail. Existing
`test_utc.py` and `test_engine.py` were re-run to confirm the migration left
no regressions.

## Files touched

- `src/aeat/core/time/test_clock.py` (created)

## Collision check

No non-authored WIP detected before any edit.

## Test outcome

4/4 passed: `uv run --no-sync pytest src/aeat/core/time/test_clock.py -xvs`

48/48 passed: `uv run --no-sync pytest src/aeat/core/time/ src/aeat/application/workflow/test_engine.py -x -q`
