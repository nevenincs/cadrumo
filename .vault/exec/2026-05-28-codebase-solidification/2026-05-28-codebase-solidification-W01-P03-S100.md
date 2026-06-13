---
step_id: S100
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S100 — SedeNavigationError translated_message tests

## Outcome

Created `src/aeat/adapters/outbound/aeat/sede/test_auth_state.py` with six
real-behavior tests (no mocks, no skip, no xfail):

- S100-A: `storage_state_for_session` None-path carries `translated_message`
- S100-B: `storage_state_for_session` unloaded-state path carries `translated_message`
  (uses `isolated_runtime_profile`)
- S100-C: `adapters.sede.errors.no_auth_session` locale key resolves to real copy
- S100-D: `fetch_notifications_summary` carries `translated_message` on None path
- S100-E: `fetch_iva_compensation_wallet` carries `translated_message` on None path
- S100-F: `walk_expedientes_tree` carries `translated_message` on None path

All six tests pass.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/test_auth_state.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/adapters/outbound/aeat/sede/test_auth_state.py -v`
→ 6 passed.
