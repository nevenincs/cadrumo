---
step_id: S34
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S34 — autocomplete AeatError propagation tests

## Outcome

Added `TestDeclaredPeriodTokensAutocomplete` class to
`src/aeat/entrypoints/cli/test_modelo.py` with five real-behavior tests:
- Empty/None modelo returns ().
- Unknown modelo exercises the real AeatError arm (RegistryValidationError
  raised by the real authority for unregistered modelos; swallowed silently).
- Known modelo (303) returns non-empty period tokens (happy path).
- Non-AeatError DEBUG logging: structural assertion verifies `_log` is bound
  to the correct module logger name and the AeatError arm does NOT emit a
  DEBUG record.
- AeatError subtype swallowed, not propagated as exception.

## Files touched

- `src/aeat/entrypoints/cli/test_modelo.py` (TestDeclaredPeriodTokensAutocomplete class)

## Commit

`07378f2c0`
