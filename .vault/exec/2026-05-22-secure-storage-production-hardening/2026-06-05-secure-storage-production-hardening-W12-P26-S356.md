---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S356'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S356 - Close AFR-254 for modelo work units

Scope: close `AFR-254` for `src/aeat/domain/modelos/_repository.py` with signals
`secure-object, manifest-bucket`, target `runtime-default`, and owner `W12.P21.S84`.

## Description

- Audited `WorkUnitCatalogueRepository` default construction and confirmed it resolves
  explicit or active profile buckets through `resolve_modelo_repository_bucket_id`.
- Confirmed repository construction delegates runtime-owned secure-object creation to
  `secure_objects_for_modelo_bucket` and stores FINANCIAL envelopes under a stable
  namespace and catalogue object key.
- Hardened persistence error surfacing to use
  `errors.fail.fail_modelo_work_unit_persistence` with structured context instead of
  interpolating raw storage exception text into operator-facing errors.
- Added real encrypted-storage drift tests for corrupted inner envelope classification
  and unsupported inner envelope schema version.
- Closed `W12.P26.S356` through `vaultspec-core vault plan step check` and updated the
  `AFR-254` register status to `closed`.

## Outcome

`AFR-254` is closed as `runtime-default`. The work-unit catalogue remains
bucket-scoped, runtime-created, encrypted, FINANCIAL-class storage. The S356 code
change improves convention compliance by routing user-facing persistence failures
through the centralized locale key and redacted structured context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_repository.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/_runtime_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The locale audit passed in the shared worktree after adjacent modelo-resume locale
work had already been applied through the mandated `python -m aeat.locales` path.
Those locale files are not part of the S356 repository runtime slice.
