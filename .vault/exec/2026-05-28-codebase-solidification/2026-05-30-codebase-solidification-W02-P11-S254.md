---
step_id: S254
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S254

## Outcome

Created `test_cluster_envelopes.py` with 9 real-behavior tests covering the full master_key cluster:
- `test_cluster_error_envelope_round_trips` parametrized over 6 error types: `MasterKeyReentrantError`, `MasterKeyTypeError`, `KeyDerivationError`, `EncryptionError`, `StorageValidationError`, `SecretStoreError`. Each asserts code is in `ERROR_REGISTRY` and `build_error_envelope` produces non-empty `message`.
- `test_master_key_reentrant_error_is_secret_store_error_subtype` — inheritance hierarchy check.
- `test_master_key_type_error_is_storage_error_and_type_error` — dual-inheritance check.

## Test result

180 total master_key tests pass (21 net new across S245/S248/S250/S254).

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py` — created
