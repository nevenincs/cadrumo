---
step_id: S250
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S250

## Outcome

Created `test_dek_wrap_errors.py` with 5 real-behavior tests asserting `EncryptionError` at every migrated `_dek_wrap.py` raise:
- `test_wrap_dek_raises_encryption_error_for_short_kek` (line 74).
- `test_wrap_dek_raises_encryption_error_for_short_dek` (line 76).
- `test_wrap_dek_raises_encryption_error_for_empty_bucket_id` (line 49).
- `test_encryption_error_is_registered` — ErrorCode in ERROR_REGISTRY.
- `test_encryption_error_envelope_round_trip` — valid ErrorEnvelope.

## Test result

5 new tests pass.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py` — created
