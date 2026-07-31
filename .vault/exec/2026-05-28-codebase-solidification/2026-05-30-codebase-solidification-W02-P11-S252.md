---
step_id: S252
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:9f0d4e6553f7f0544c3f090891fe5df4db4f6b2ef789eabf9f17c0eefd3af6f8'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S252

## Outcome

Migrated 1 `TypeError` raise in `_zeroise.py` to `MasterKeyTypeError`:
- Line 46: `not isinstance(buffer, bytearray)` guard now raises `MasterKeyTypeError`.

`MasterKeyTypeError` inherits from `(StorageError, TypeError)` so pre-existing `pytest.raises(TypeError)` assertions in `test_zeroise.py` continue to pass without modification.

## Test result

6 zeroise tests pass without changes.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_zeroise.py` — 1 TypeError → MasterKeyTypeError
