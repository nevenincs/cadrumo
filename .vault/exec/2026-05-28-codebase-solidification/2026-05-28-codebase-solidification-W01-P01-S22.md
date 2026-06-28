---
step_id: "S22"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S22

**Status**: closed

## What was done

Added three real-behaviour tests to `src/aeat/domain/profile/test_keys.py`:

- `test_profile_keys_registration_error_is_in_error_registry` — asserts `INTERNAL_PROFILE_KEYS_REGISTRATION` is present in `ERROR_REGISTRY`.
- `test_profile_keys_registration_error_round_trips_through_build_error_envelope` — calls `build_error_envelope(ProfileKeysRegistrationError())` and asserts `code`, `category`, `message`, and `retryable`.
- `test_double_registration_with_conflicting_tuple_raises_profile_keys_registration_error` — calls `register_profile_keys(())` (empty tuple guaranteed to differ from real registry) and asserts `pytest.raises(ProfileKeysRegistrationError)`.

All 15 tests in the file pass (`uv run --no-sync pytest src/aeat/domain/profile/test_keys.py -xvs`).

## Files touched

- `src/aeat/domain/profile/test_keys.py` — three new real-behaviour tests

## Commit

`70ce08b71`
