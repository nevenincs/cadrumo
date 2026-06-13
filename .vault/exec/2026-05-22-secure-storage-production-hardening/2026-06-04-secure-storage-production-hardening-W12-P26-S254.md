---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S254'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s254-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S254`

Closed `AFR-152` for the atomic setup service.

## Description

- Reviewed `src/aeat/application/setup/_service.py` as an active-profile and manifest-bucket setup surface.
- Added central debug logging when reserved auth-provider configuration is refused but kept non-fatal.
- Kept certificate paths and secrets out of the log payload; only the provider token is recorded.
- Added a real setup-service regression test using the existing file-backed profile storage root and `caplog`.
- Closed `S254` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-152` is closed as `manifest-discovery`. The setup service still provisions profile/bucket state through `profile_create_storage_span` and workflow profile registration, while the previously silent reserved-auth-provider branch is now observable through the centralized redacting logger.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/setup/_service.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The non-fatal reserved-provider behavior was preserved for compatibility, but it is no longer silent.
