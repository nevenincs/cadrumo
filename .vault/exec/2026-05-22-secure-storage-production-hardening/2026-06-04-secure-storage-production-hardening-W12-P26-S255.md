---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S255'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s255-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S255`

Closed `AFR-153` for the operator state projection.

## Description

- Reviewed `src/aeat/application/state_projection.py` as a runtime, active-profile, manifest-bucket, plain-file, and remote-provider read projection.
- Removed raw active bucket id rendering from the profile-label debug log.
- Added DEBUG logging when registry snapshot absence causes ledger preflight to be skipped for modelo readiness.
- Added a real state-projection regression test for the no-snapshot preflight-skip path.
- Closed `S255` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-153` is closed as `remote-mirror`. The projection remains read-only and centralized, while failure-to-resolve and skip paths are observable without exposing active bucket ids in log messages.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/state_projection.py src/aeat/application/test_state_projection.py`
- `uv run --no-sync pytest -q src/aeat/application/test_state_projection.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The state projection still deliberately degrades registry snapshot absence to "ledger preflight not required"; the change makes that degradation visible at DEBUG level.
