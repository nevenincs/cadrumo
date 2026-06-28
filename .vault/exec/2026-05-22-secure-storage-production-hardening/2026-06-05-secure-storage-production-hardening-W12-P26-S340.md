---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S340'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S340 - Close AFR-238 for filing runtime helpers

Scope: close `AFR-238` for `src/aeat/domain/filing/_runtime_repository.py` with
signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`,
and owner `W12.P21.S84`.

## Description

- Audited filing runtime helper resolution for explicit bucket ids, active profile
  bucket ids, and secure-object repository construction.
- Preserved the locale-key refusal path through `ModeloDraftError` and
  `application.workflow.errors.no_active_profile_bucket`.
- Added structured refusal context distinguishing blank explicit bucket ids from
  missing active profile buckets.
- Added real helper tests for explicit bucket acceptance, blank explicit bucket
  refusal, active-profile resolution, missing active-profile refusal, and unready
  runtime route refusal.
- Closed `W12.P26.S340` through `vaultspec-core vault plan step check` and updated
  the `AFR-238` register status to `closed`.

## Outcome

`AFR-238` is closed. Filing runtime helpers remain centralized around active-profile
bucket resolution and runtime-created secure-object repositories, and refusal errors
now carry structured diagnostic context without bypassing localization or exception
hierarchy conventions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/filing/_runtime_repository.py src/aeat/domain/filing/test_runtime_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/filing/_complementaria_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/filing/test_runtime_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "resolve_filing_repository_bucket_id secure_objects_for_filing_bucket active profile bucket StorageValidationError runtime route ModeloDraftError context" --type code --port 8766 --max-results 8`

## Notes

This step intentionally mirrors the already-hardened application filing runtime helper
context shape so domain and application repository route refusals diagnose the same
failure classes.
