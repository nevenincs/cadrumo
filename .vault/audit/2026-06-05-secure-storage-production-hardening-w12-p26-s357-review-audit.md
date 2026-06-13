---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S357]]'
---

# `secure-storage-production-hardening` `W12.P26.S357` Review

## S357-001 | PASS | Modelo runtime helper delegates secure storage to runtime

`secure_objects_for_modelo_bucket` imports and calls
`secure_object_repository_for_bucket` at runtime. It does not instantiate SQL
repositories or derive physical storage routes itself, so route readiness, active bucket
session checks, sealed-session checks, and backend security checks stay centralized in
the storage runtime layer.

## S357-002 | PASS | Active-profile failure modes are localized and structured

`resolve_modelo_repository_bucket_id` now distinguishes blank explicit bucket ids from
missing active profile buckets with structured `reason` context while preserving the
existing `application.workflow.errors.no_active_profile_bucket` locale key. Callers still
receive their production `ModeloError` subclass.

## S357-003 | PASS | Tests exercise real helper and runtime behavior

The new test module imports production helper functions and production
`WorkUnitPersistenceError`. It verifies explicit bucket trimming, blank-bucket refusal,
active-profile fallback through centralized settings, missing-active-profile refusal,
and the storage runtime factory's unready-runtime rejection. No fakes, mocks, stubs,
monkeypatches, skips, or mirrored business logic were introduced.

## S357-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/modelos/_runtime_repository.py src/aeat/domain/modelos/test_runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_runtime_repository.py` passed with 5 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime.py -k "runtime_repository_factory_refuses_unready_runtime or runtime_repository_factory_rechecks"` passed with 6 selected tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"` passed with 10 selected tests.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S357 slice.

Disposition: close `AFR-255` as `runtime-default`.
