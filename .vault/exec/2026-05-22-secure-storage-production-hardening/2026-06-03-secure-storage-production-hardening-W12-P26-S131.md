---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S131'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s131-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S131`

Closed `AFR-029` for the Google OAuth error module.

## Description

- Reviewed `src/aeat/adapters/outbound/google/_errors.py` against the `active-profile` scanner signal.
- Classified the signal as documentation wording on typed OAuth errors rather than profile, bucket, manifest, or storage implementation.
- Verified the error hierarchy derives from `AeatError` and is exercised by registry, records, package allowlist, and CLI Google localisation tests.
- Recorded the S131 review and updated the affected-file register row to `closed`.

## Outcome

`AFR-029` is closed as a `manifest-discovery` false positive for this file.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry_enforcement.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_records.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_errors.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/test_records.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py`

## Notes

No source edits were required for this step.
