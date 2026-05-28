---
step_id: S40
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S40 — ObservationKeyError test coverage

## Outcome

Created `src/aeat/application/calculations/test_observations_repository.py`
with 15 real-behavior tests. Tests assert: `ERROR_OBSERVATION_KEY` is present
in `ERROR_REGISTRY`; `build_error_envelope` succeeds; each of the five
validation sites raises `ObservationKeyError` on invalid input; `observation_key`
succeeds on boundary years; `iva_wallet_decision_key` succeeds with valid NIF;
`iva_wallet_decision_event_key` succeeds; legacy key guard raises for out-of-range
years; `ObservationKeyError` is a subtype of `ValueError`.

## Files touched

- `src/aeat/application/calculations/test_observations_repository.py`

## Verification

`uv run --no-sync pytest src/aeat/application/calculations/test_observations_repository.py -xvs` — 15 passed.
