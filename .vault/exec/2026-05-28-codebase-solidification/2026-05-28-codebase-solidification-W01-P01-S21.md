---
step_id: "S21"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S21

**Status**: closed

## What was done

Introduced `ProfileKeysRegistrationError(CoreError)` in `src/aeat/domain/profile/_errors.py`, replacing the bare `RuntimeError` at `src/aeat/domain/profile/_keys.py:122` with `raise ProfileKeysRegistrationError()`.

Registered the new error under code `INTERNAL_PROFILE_KEYS_REGISTRATION` (category `INTERNAL`) in `src/aeat/core/errors/registry/_domain.py`.

Also added the registry entry for `_BinaryXlsConversionError` from peer-agent WIP that blocked the profile conftest import chain.

## Files touched

- `src/aeat/domain/profile/_errors.py` — added `ProfileKeysRegistrationError(CoreError)`
- `src/aeat/domain/profile/_keys.py` — replaced `RuntimeError` with `ProfileKeysRegistrationError()`
- `src/aeat/core/errors/registry/_domain.py` — registry entries for `ProfileKeysRegistrationError` and `_BinaryXlsConversionError`

## Commit

`70ce08b71`
