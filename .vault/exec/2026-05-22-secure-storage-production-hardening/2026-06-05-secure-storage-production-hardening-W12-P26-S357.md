---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S357'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S357 - Close AFR-255 for modelo runtime repository

Scope: close `AFR-255` for `src/aeat/domain/modelos/_runtime_repository.py` with
signals `secure-object, active-profile, manifest-bucket`, target `runtime-default`,
and owner `W12.P21.S84`.

## Description

- Audited the modelo runtime helper that resolves explicit bucket ids, active-profile
  bucket ids, and runtime-owned secure-object repositories for modelo persistence.
- Confirmed `secure_objects_for_modelo_bucket` delegates to
  `secure_object_repository_for_bucket`, preserving the storage runtime's route/session
  validation instead of constructing SQL secure-object repositories directly.
- Hardened `resolve_modelo_repository_bucket_id` so blank explicit bucket ids and
  missing active profiles raise the caller's production `ModeloError` subclass with
  `application.workflow.errors.no_active_profile_bucket` and structured reason context.
- Added direct modelo runtime-helper tests using production `WorkUnitPersistenceError`
  plus the runtime factory's unready-runtime refusal path.
- Closed `W12.P26.S357` through `vaultspec-core vault plan step check` and updated
  the `AFR-255` register status to `closed`.

## Outcome

`AFR-255` is closed as `runtime-default`. The helper remains a narrow runtime boundary:
callers can provide an explicit bucket or fall back to the centralized active-profile
setting, while secure-object construction remains owned by the storage runtime.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_runtime_repository.py src/aeat/domain/modelos/test_runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_runtime_repository.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime.py -k "runtime_repository_factory_refuses_unready_runtime or runtime_repository_factory_rechecks"`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`

## Notes

No localization file edits were required for S357 because the helper already uses the
centralized `application.workflow.errors.no_active_profile_bucket` locale key.
