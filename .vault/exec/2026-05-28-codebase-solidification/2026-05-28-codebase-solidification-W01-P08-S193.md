---
step_id: S193
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P08.S193 — TypeGuard replaces bare cast in _errors.py

## Outcome

Added `_is_memoised_wrapper(obj) -> TypeGuard[Callable[..., object]]` to
`src/aeat/entrypoints/cli/_errors.py`. The `command_error_boundary` memoisation
path now calls `_is_memoised_wrapper(existing)` before the cast, providing a
runtime callable check and a documented rationale comment
(`CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER`). The `cast(Callable[P, R], existing)`
is retained only because `dict[int, Callable[..., object]]` cannot express the
full ParamSpec `P` — documented as Wave 2 follow-up.

## Verification

All 13 tests pass. Commit: b00a08f94
