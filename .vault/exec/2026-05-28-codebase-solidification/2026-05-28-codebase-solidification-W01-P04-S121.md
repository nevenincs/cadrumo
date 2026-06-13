---
step_id: S121
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S121 — NIF-IVA oracle caller migration

## Outcome

Kappa's migration is clean. `AeatNifIvaReplayDriver.collect_observation` calls
`decode_replay_json_payload` (which calls `ReplayPayload.model_validate`)
and constructs `AeatNifIvaObservation` from the typed envelope's `.observed`
mapping and `.raw_evidence_locator`. No manual dict unpacking, no `isinstance`
bypass, no raw key access on unvalidated dicts.

## Files touched

- `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py` (read-only verification)

## Collision check

Clean — `git diff` on the file before read returned empty.

## Test outcome

10 tests passed: `test_aeat_nif_iva_oracle.py` (pre-existing suite, all green).
