---
step_id: S246
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S246

## Outcome

Migrated 2 `ValueError` raises in `_kdf.py` to `KeyDerivationError`:
- Line 44: unsupported KDF algorithm guard.
- Line 48: unsupported KDF output_length guard.

Added `from ..errors import KeyDerivationError` import. Updated docstring from `ValueError` to `KeyDerivationError`. Updated pre-existing `test_kdf.py` tests at lines 101 and 116 to catch `KeyDerivationError` instead of `ValueError`.

## Test result

6 existing kdf tests pass (2 assertions updated to correct type).

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_kdf.py` — 2 ValueError → KeyDerivationError
- `src/aeat/adapters/persistence/storage/master_key/test_kdf.py` — 2 pytest.raises updated
