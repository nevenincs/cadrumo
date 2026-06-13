---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S353'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S353 - Close AFR-251 for modelo calculation revisions

Scope: close `AFR-251` for `src/aeat/domain/modelos/_calculation_repository.py`
with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner
`W12.P21.S84`.

## Description

- Audited `CalculationRevisionCatalogueRepository` default construction and confirmed
  it resolves explicit or active profile buckets through
  `resolve_modelo_repository_bucket_id`.
- Confirmed repository construction delegates runtime-owned secure-object creation to
  `secure_objects_for_modelo_bucket` and stores FINANCIAL envelopes under a stable
  namespace and catalogue object key.
- Hardened persistence error surfacing to use
  `errors.fail.fail_modelo_calculation_revision_persistence` with structured context
  instead of interpolating raw storage exception text into operator-facing errors.
- Added real encrypted-storage drift tests for corrupted inner envelope classification
  and unsupported inner envelope schema version.
- Closed `W12.P26.S353` through `vaultspec-core vault plan step check` and updated the
  `AFR-251` register status to `closed`.

## Outcome

`AFR-251` is closed as `runtime-default`. The calculation-revision catalogue remains
bucket-scoped, runtime-created, encrypted, FINANCIAL-class storage; the S353 code
change improves convention compliance by routing user-facing persistence failures
through the centralized locale key and redacted structured context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/_runtime_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "CalculationRevisionCatalogueRepository secure_objects_for_modelo_bucket runtime bucket FINANCIAL translated persistence error" --type code --port 8766 --max-results 8`

## Notes

The injected `objects` constructor path is retained for existing real-behavior tests
and application seams. Production default construction uses the runtime helper and does
not construct a raw SQL repository directly.
