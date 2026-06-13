---
step_id: S194
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P08.S194 — test TypeGuard narrowing in test_errors.py

## Outcome

Created `src/aeat/entrypoints/cli/test_errors.py` with:
- `test_is_memoised_wrapper_narrows_callable`: asserts True for functions, lambda, callable instances.
- `test_is_memoised_wrapper_rejects_non_callable`: asserts False for int, str, None, object.
- `test_command_error_boundary_memoised_wrapper_returns_same_object`: exercises the memo path end-to-end; asserts `first_wrapped is second_wrapped` and correct return value.
- `test_cast_rationale_marker_present_in_errors_source`: CI source-text assertion.

No mocks, no skips, no xfail.

## Verification

All 13 tests pass. Commit: b00a08f94
