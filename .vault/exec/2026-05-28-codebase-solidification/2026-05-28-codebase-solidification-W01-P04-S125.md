---
step_id: S125
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S125 — Renta WEB Open oracle caller migration

## Outcome

Kappa's migration is clean. `RentaWebOpenReplayDriver.collect_observation` calls
`decode_replay_json_payload` (which delegates to `ReplayPayload.model_validate`)
and constructs `RentaWebOpenObservation` from the typed envelope's `.observed`
mapping and `.raw_evidence_locator`. No manual dict unpacking, no isinstance
bypass, no raw key access.

## Files touched

- `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py` (read-only verification)

## Collision check

Clean — `git diff` on the file before read returned empty.

## Test outcome

Pre-existing Renta WEB Open test suite passes (25 tests green).
