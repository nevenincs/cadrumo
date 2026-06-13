---
step_id: S244
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P11.S244

## Outcome

Migrated 2 `RuntimeError` raises in `_master_key.py` to `MasterKeyReentrantError`:
- Line 974 (`EphemeralMasterKeyProvider.__enter__`): lazy import + raise `MasterKeyReentrantError(type(self).__name__)`.
- Line 1294 (module-level provider context helper): lazy import + raise `MasterKeyReentrantError(type(provider).__name__)`.

Both sites pass the provider class name as `provider_name` into the structured context.

## Test result

159 existing master_key tests pass.

## Files touched

- `src/aeat/adapters/persistence/storage/master_key/_master_key.py` — 2 RuntimeError → MasterKeyReentrantError
