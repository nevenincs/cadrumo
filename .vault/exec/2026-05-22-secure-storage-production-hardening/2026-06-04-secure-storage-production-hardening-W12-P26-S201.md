---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S201'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s201-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S201`

Closed `AFR-099` for calculation observations and IVA wallet decisions.

## Description

- Reviewed `src/aeat/application/calculations/_observations_repository.py`
  against the `runtime-default` classification for secure-bound storage.
- Updated wallet decision hashing and envelope serialization/decode sites to use
  the centralized `UTF_8_ENCODING` constant.
- Added `IvaWalletDecisionRepository` latest-decision and decision-history reads
  to the runtime migration missing-session refusal and route/session mismatch
  refusal cases.
- Extended the active-profile isolation gate with real
  `IvaCompensationReconciliationDecision` objects persisted through the
  repository under two runtime profiles, including immutable history replay.
- Cleared the locale validation blocker through `python -m aeat.locales set` and
  confirmed all locale catalogues pass `python -m aeat.locales audit`.

## Outcome

`AFR-099` is closed. Calculation observations plus IVA wallet latest decisions
and immutable history are now covered by the same secure-bound runtime-default
refusal and active-profile isolation gates, and the wallet decision repository no
longer carries local string literals for UTF-8 encoding.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/calculations/test_observations_repository.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest src/aeat/application/calculations/test_observations_repository.py src/aeat/application/calculations/test_observations_repository_roundtrip.py -q`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "iva_wallet_decision or calculation_observations or application_repository_defaults_isolate_active_profile_writes" -q`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -q`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The locale catalogue files were changed through the required
`python -m aeat.locales` CLI. That tool normalized neighboring YAML formatting
while inserting the missing keys; the follow-up audit reports all locales as
`ok`.

No direct secure-object repository construction, naked environment access,
silent exception swallowing, raw user-facing strings, `noqa`, `pragma`,
monkeypatches, fakes, mocks, skips, or xfails were introduced.
