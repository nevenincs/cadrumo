---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S269'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s269-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S269`

Closed `AFR-167` for profile repository remote-mirror/runtime custody.

## Description

- Hardened profile inventory warnings so unreadable manifest diagnostics redact bucket ids and log stable error types instead of raw exception text.
- Replaced a broad duplicate-tax-id scan `except Exception` with typed storage/profile failure classes and warning evidence.
- Routed best-effort rollback directory cleanup through a helper that logs cleanup failures at debug level without masking the original create failure.
- Added a real profile repository test asserting the unreadable-profile skip warning redacts the profile id while preserving the failure type.
- Closed `S269` through `vaultspec-core vault plan step check` and manually aligned `AFR-167`.

## Outcome

`AFR-167` is closed as `remote-mirror`. The profile repository remains the sole cross-store writer for manifests, active-profile pointer state, secure profile records, and profile bucket cleanup, with narrowed exception handling and scrubbed diagnostics on skip/degradation paths.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_profile_repository.py src/aeat/application/user_profile/test_profile_repository.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_profile_repository.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The broader plan check still reports only the existing `PLAN022` monotonic-order warning.
