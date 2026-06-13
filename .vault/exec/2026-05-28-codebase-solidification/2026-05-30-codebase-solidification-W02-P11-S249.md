---
step_id: S249
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S249

## Outcome

Migrated 4 `ValueError` raises in `_dek_wrap.py` to `EncryptionError`:
- `_associated_data` line 49: empty bucket_id guard.
- `wrap_dek` line 74: wrong-size kek guard.
- `wrap_dek` line 76: wrong-size dek guard.
- `unwrap_dek` line 105: wrong-size kek guard.

Updated pre-existing `test_dek_wrap.py` tests (lines 128, 133, 138) to catch `EncryptionError` instead of `ValueError` (since `EncryptionError` does not inherit `ValueError`).

## Test result

12 existing dek_wrap tests pass (3 assertions updated to correct type).

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py` — 4 ValueError → EncryptionError
- `src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py` — 3 pytest.raises updated
