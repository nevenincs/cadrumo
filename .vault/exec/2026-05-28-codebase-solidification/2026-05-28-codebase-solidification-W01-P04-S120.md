---
step_id: S120
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S120 — ReplayPayload roundtrip tests

## Outcome

Added 11 real-behavior tests to `test_live_parity.py` covering the
`ReplayPayload` boundary contract:

- Well-formed payload accepted (with and without locator)
- Missing `observed` field raises `ValidationError`
- Non-string values in `observed` rejected by strict mode
- Non-string keys in `observed` rejected
- Extra top-level keys rejected by `extra="forbid"`
- `observed` as a list rejected
- Non-UTF-8 bytes raise `RegistryValidationError`
- JSON array at top level raises `RegistryValidationError`
- Malformed JSON raises `RegistryValidationError`
- Anti-tautology proof: mutating the payload to drop `observed` surfaces failure
  AND the valid case validates (proving neither branch is vacuous)

No mocks, no skips, no xfail markers. All cases use `pytest.raises` with
pydantic-native `ValidationError` or `RegistryValidationError`.

## Files touched

- `src/aeat/domain/calculations/registry/test_live_parity.py` (11 tests added)

## Collision check

Clean — confirmed by initial `git diff` before first edit.

## Test outcome

28/28 passed: `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_live_parity.py -xvs`
