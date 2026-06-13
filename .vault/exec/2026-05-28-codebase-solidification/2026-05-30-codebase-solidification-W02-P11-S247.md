---
step_id: S247
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S247

## Outcome

Migrated raises in `_kdf_params.py` to storage errors:
- `_check_salt_length` validator (line 68): `ValueError` → `StorageValidationError` (inherits `ValueError`, preserving pydantic `ValidationError` wrapping).
- `_decode_salt` validator (line 82): `TypeError` → `StorageValidationError` (same rationale — pydantic validators must raise `ValueError` subclasses to be wrapped in `ValidationError`).

`KeyDerivationError` extends `EncryptionError` without inheriting `ValueError`, so pydantic validators inside `KdfParams` use `StorageValidationError` which satisfies both the typed-storage contract and pydantic's validator protocol.

## Test result

5 existing kdf_params tests pass (no assertion changes needed — all catch `ValidationError`).

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py` — 2 raises migrated
