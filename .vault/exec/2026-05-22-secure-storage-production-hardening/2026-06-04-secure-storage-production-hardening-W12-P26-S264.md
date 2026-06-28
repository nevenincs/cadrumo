---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S264'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s264-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S264`

Closed `AFR-162` for the censo-sync manifest/plain-file profile surface.

## Description

- Audited `src/aeat/application/user_profile/_censo_sync.py` for translated errors, swallowed exceptions, censo snapshot persistence flow, and duplicated decimal parsing.
- Replaced the blank `bucket_id` raw-string refusal with a `CensoSyncError` carrying a locale key.
- Added the censo blank-bucket locale key through `python -m aeat.locales`.
- Factored duplicated home-office raw-affectation parsing into a single helper.
- Added debug logs for non-decimal and invalid censo ratio inputs instead of silently swallowing parse failures.
- Added real-behavior tests for the translated constructor error and debug trace on malformed censo ratio inputs.
- Updated the censo error docstring to point at the canonical `aeat config profile create` surface.
- Closed `S264` through `vaultspec-core vault plan step check` and manually aligned `AFR-162`.

## Outcome

`AFR-162` is closed. The censo-sync service now preserves the existing no-write behavior for absent or malformed ratio inputs while making malformed remote data observable at debug level, and its constructor refusal is enrolled in the locale catalogue.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_censo_sync.py src/aeat/application/user_profile/_censo_errors.py src/aeat/application/user_profile/test_censo_sync.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_censo_sync.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
