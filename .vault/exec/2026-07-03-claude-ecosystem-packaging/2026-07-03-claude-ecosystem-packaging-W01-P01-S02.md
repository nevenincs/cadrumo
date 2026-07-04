---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S02'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Root aeat_local_storage_root at the platform user-data directory for installed runs while preserving the PROJECT_ROOT var/storage default for a source checkout

## Scope

- `src/aeat/core/config.py`

## Description

- Switch `aeat_local_storage_root` on `src/aeat/core/config.py` from a static default to a `default_factory` over `default_storage_root()`.
- Preserve behavior for a checkout run: `default_storage_root()` resolves byte-identically to `PROJECT_ROOT / var / storage`, verified live.
- Route an installed run to `<platform-base>/aeat/storage` via the resolver added in `S01`.
- Leave `AEAT_LOCAL_STORAGE_ROOT` and every per-directory override (tokens, logs, secrets, blobs, audit) unchanged; they still take precedence over the derived default.
- Commit `263466d32b`.

## Outcome

- 41 config, token, and storage tests passed with zero regressions.

## Notes

No incidents. No skipped work.
