---
step_id: S248
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:23be9783b897b58f842c5cf3c1e7e73b6688452a81cffd53f3d05dc6c1b44346'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S248

## Outcome

Created `test_kdf_errors.py` with 4 real-behavior tests asserting `KeyDerivationError` at every migrated `_kdf.py` raise:
- `test_derive_kek_raises_key_derivation_error_for_unsupported_algorithm` (line 44).
- `test_derive_kek_raises_key_derivation_error_for_unsupported_output_length` (line 48).
- `test_key_derivation_error_is_registered` — ErrorCode in ERROR_REGISTRY.
- `test_key_derivation_error_envelope_round_trip` — valid ErrorEnvelope.

## Test result

4 new tests pass.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py` — created
