---
step_id: S243
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S243

## Outcome

Created `src/aeat/adapters/persistence/storage/master_key/_errors.py` with:
- `MasterKeyReentrantError(SecretStoreError)` — raised on re-entrant context-manager use; carries `provider_name` in context dict.
- `MasterKeyTypeError(StorageError, TypeError)` — raised when a master-key operation receives a wrong type; dual inheritance preserves `TypeError` catchability.

Both classes registered in `src/aeat/core/errors/registry/_adapters.py` under `INTERNAL_MASTER_KEY_REENTRANT` and `INTERNAL_MASTER_KEY_TYPE`. Locale keys `errors.internal.internal_master_key_reentrant` and `errors.internal.internal_master_key_type` added to all four locales (en, es, ca, hu) via `python -m aeat.locales set`.

## Test result

159 existing master_key tests pass.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_errors.py` — created
- `src/aeat/core/errors/registry/_adapters.py` — 2 new error code registrations appended
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — 2 locale keys each
