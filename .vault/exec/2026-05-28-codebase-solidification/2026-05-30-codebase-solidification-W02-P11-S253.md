---
step_id: S253
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S253

## Outcome

Migrated 1 `ValueError` raise in `_recovery_record.py` to `StorageValidationError`:
- `_validate_b64` line 34: non-canonical base64 guard.

`StorageValidationError` inherits from `ValueError`, so pydantic wraps it in `ValidationError` when the validator fires — `test_recovery_record.py` tests expecting `ValidationError` continue to pass without modification.

## Test result

14 recovery_record tests pass without changes.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py` — 1 ValueError → StorageValidationError
