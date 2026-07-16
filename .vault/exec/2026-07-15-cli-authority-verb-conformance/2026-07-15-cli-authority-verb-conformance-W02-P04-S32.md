---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S32'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Centralize provider teardown in the shared exit boundary so production and ephemeral providers atomically detach their bookkeeping, close only their exact owned BucketSession before unwinding activation, reuse that boundary after failed entry, and do not recreate the retired OS-keyring cache

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_ephemeral.py`

## Description

- Detach provider bookkeeping before cleanup so repeated and reentrant exits are no-ops.
- Close only the exact provider-owned bucket session before unwinding its activation token.
- Route failed provider entry and the ephemeral provider through the same teardown boundary.
- Preserve nested activation restoration without recreating the retired OS-keyring cache.

## Outcome

- Landed the implementation in `a2ca290ef7` after scope reconciliation in `a34e9b003f`.
- The complete master-key suite passed with 187 tests.
- Ruff and diff checks passed.
- Production and ephemeral providers now share one close-and-detach implementation.

## Notes

- No data loss, skipped tests, persistent failures, compatibility aliases, or runtime scaffolds remain.
