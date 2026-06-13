---
step_id: "S30"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S30

**Status**: closed

## What was done

Extended `src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`
with four new real-behavior tests:

- `test_recovery_verification_error_is_in_error_registry` — asserts
  `AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION` is in `ERROR_REGISTRY`,
  category is `AUTH`, message key matches the locale key.
- `test_recovery_verification_error_round_trips_through_build_error_envelope`
  — constructs `RecoveryVerificationError`, calls `build_error_envelope`,
  asserts `code == "AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION"` and
  `retryable is False`.
- `test_storage_validation_error_from_decode_mnemonic_is_reclassified`
  — exercises all three `StorageValidationError` paths from
  `decode_mnemonic` (wrong word count, unknown word, checksum mismatch)
  and asserts each re-raises as `RecoveryVerificationError`.
- `test_unexpected_exception_from_decode_mnemonic_propagates_unchanged`
  — injects a `KeyError` via `pytest.MonkeyPatch.setattr` on
  `_recovery_facade.decode_mnemonic`, calls `unwrap_recovery_envelope`,
  and asserts `KeyError` propagates unchanged (proving the narrowed
  `except StorageValidationError` does not absorb unexpected exceptions).

14/14 tests pass. No mocks (`unittest` banned), no skips, no xfail,
no tautological assertions. `monkeypatch.setattr` is the approved
pytest-native injection mechanism.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`
  — 4 new tests added; import of `_facade_module`, `ERROR_REGISTRY`,
  `build_error_envelope`

## Commit

`f3698c297`
