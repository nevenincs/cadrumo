---
step_id: S123
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S123 — GROI oracle caller migration

## Outcome

Kappa's migration is clean. `GroiReplayDriver.collect_observation` calls
`decode_replay_json_payload` (which delegates to `ReplayPayload.model_validate`)
and constructs `GroiObservation` from the typed envelope. No manual dict
unpacking, no isinstance bypass.

Drift found and fixed: two pre-existing GROI tests asserted stale
`RegistryValidationError` messages (`"observed object"`, `"string-keyed strings"`)
that no longer exist after kappa's migration — those paths now raise pydantic
`ValidationError`. Both tests were updated to catch `ValidationError` with
correct match strings.

## Files touched

- `src/aeat/domain/calculations/registry/_groi_oracle.py` (read-only verification)
- `src/aeat/domain/calculations/registry/test_groi_oracle.py` (2 stale tests fixed)

## Collision check

Clean — `git diff` on both files before edits returned empty.

## Test outcome

All GROI tests pass after fixing the two stale error-match strings.
