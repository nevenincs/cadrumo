---
step_id: S39
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S39 — ObservationKeyError introduction

## Outcome

Added `ObservationKeyError(CoreValidationError)` to
`src/aeat/application/calculations/_errors.py`. Replaced all five bare
`raise ValueError(...)` guards in `_observations_repository.py` (in
`observation_key`, `iva_wallet_decision_key`, `iva_wallet_decision_event_key`,
and `_legacy_iva_wallet_decision_key`) with `raise ObservationKeyError(...)`.
Registered `ERROR_OBSERVATION_KEY` (`ErrorCategory.ERROR`) in
`src/aeat/core/errors/registry/_application.py` with
`message_key="errors.error.error_observation_key"`. Ran locale scaffold and
filled real messages in en, es, ca, and hu.

## Files touched

- `src/aeat/application/calculations/_errors.py`
- `src/aeat/application/calculations/_observations_repository.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

No bare `ValueError` raises remain in `_observations_repository.py`. Lint clean.
