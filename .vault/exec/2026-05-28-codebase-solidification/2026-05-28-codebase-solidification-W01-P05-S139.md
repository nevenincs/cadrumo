---
step_id: S139
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S139

Migrated four local `_ensure_utc` definitions to the canonical helpers
in `src/aeat/core/time/_utc.py` introduced by coder-alpha (commit `2e0d737a2`).

## Files modified

- `src/aeat/adapters/outbound/aeat/auth/certificate.py` — deleted local coerce-semantic `_ensure_utc`; added import of `_coerce_utc_aware`; replaced two call-sites (`not_before`, `not_after` in `load_certificate` and `verify_handshake`).
- `src/aeat/adapters/persistence/storage/bucket/_manifest.py` — deleted local validate-semantic `_ensure_utc`; added import of `_validate_utc_aware`; replaced two call-sites (`_check_created_at`, `_check_last_unlocked_at`); removed now-unused `UTC` import.
- `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py` — deleted local validate-semantic `_ensure_utc`; added import of `_validate_utc_aware`; replaced one call-site (`_check_created_at`); removed now-unused `UTC` import.
- `src/aeat/application/user_profile/_aggregate.py` — deleted local validate-semantic `_ensure_utc`; added import of `_validate_utc_aware`; replaced one call-site (`_check_created_at`); removed now-unused `UTC` import.

## Outcome

No `_ensure_utc` definitions remain in the codebase outside `core/time/_utc.py`.
60 tests pass across the four affected test files.
