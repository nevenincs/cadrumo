---
step_id: "S29"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S29

**Status**: closed

## What was done

Audited `RecoveryVerificationError` hierarchy: it inherits from
`BucketError -> SecureStorageError -> AeatError` and is already
registered in the adapters registry as
`AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION` — no promotion needed.

Narrowed the broad `except Exception` at `_recovery_facade.py:120`
to `except StorageValidationError`. Enumerated all exception classes
that `decode_mnemonic` can raise: `StorageValidationError` only (three
BIP-39 failure paths: wrong word count, unknown word, checksum mismatch).
Added `StorageValidationError` to the imports from `..errors`.

Unexpected exceptions now propagate unchanged to the top-level CLI
error handler instead of being silently reclassified as
`RecoveryVerificationError`.

## Narrowed exception set

`decode_mnemonic` raises exclusively `StorageValidationError` (a
subclass of both `PersistenceError` and `ValueError`). The catch clause
is now: `except StorageValidationError`.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`
  — import `StorageValidationError`; narrow `except Exception` → `except StorageValidationError`

## Commit

`f3698c297`
