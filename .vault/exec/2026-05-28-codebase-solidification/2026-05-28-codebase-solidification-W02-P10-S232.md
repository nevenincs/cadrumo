---
step_id: S232
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S232

## Outcome

Extended `src/aeat/domain/calculations/registry/test_export_parse.py` with `test_parse_boolean_delegates_to_core_parse_bool`: asserts that tokens which overlap between the registry and core sets ("1" → True, "no" → False) resolve correctly through the wrapper, proving the delegation path is exercised.

All 44 tests in the three targeted modules passed.

## Test result

44 passed (all targeted modules).

## Files touched

- `src/aeat/domain/calculations/registry/test_export_parse.py` — one new test
