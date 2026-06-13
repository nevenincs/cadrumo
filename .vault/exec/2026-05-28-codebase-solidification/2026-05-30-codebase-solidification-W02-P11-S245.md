---
step_id: S245
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S245

## Outcome

Created `test_master_key_errors.py` with 4 real-behavior tests:
- `test_ephemeral_provider_raises_reentrant_error_on_second_enter` — exercises actual `EphemeralMasterKeyProvider.__enter__` re-entry.
- `test_master_key_reentrant_error_is_registered` — asserts ErrorCode bound in ERROR_REGISTRY.
- `test_master_key_reentrant_error_envelope_round_trip` — `build_error_envelope` produces valid `ErrorEnvelope`.
- `test_master_key_reentrant_error_carries_provider_name_in_context` — context dict carries `provider_name`.

## Test result

4 new tests pass; 159 pre-existing pass (163 total).

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py` — created
