---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S355'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S355 - Close AFR-253 for modelo filing records

Scope: close `AFR-253` for `src/aeat/domain/modelos/_filing_repository.py` with
signals `secure-object, manifest-bucket`, target `runtime-default`, and owner
`W12.P21.S84`.

## Description

- Audited `ModeloRecordCatalogueRepository` default construction and confirmed it
  resolves explicit or active profile buckets through `resolve_modelo_repository_bucket_id`.
- Confirmed repository construction delegates runtime-owned secure-object creation to
  `secure_objects_for_modelo_bucket` and stores FINANCIAL envelopes under a stable
  namespace and catalogue object key.
- Hardened persistence error surfacing to use
  `errors.fail.fail_modelo_filing_record_persistence` with structured context instead
  of interpolating raw storage exception text into operator-facing errors.
- Added real encrypted-storage drift tests for corrupted inner envelope classification
  and unsupported inner envelope schema version.
- Repaired locale catalogue drift through `python -m aeat.locales scaffold` after the
  canonical locale audit surfaced missing live-expedientes and workflow-resume keys.
- Replaced scaffolded workflow-resume placeholder values through
  `python -m aeat.locales set` and removed stale
  `cli.app.modelo.work.resume_invalid_target` leaves through
  `python -m aeat.locales remove`.
- Closed `W12.P26.S355` through `vaultspec-core vault plan step check` and updated the
  `AFR-253` register status to `closed`.

## Outcome

`AFR-253` is closed as `runtime-default`. The filing-record catalogue remains
bucket-scoped, runtime-created, encrypted, FINANCIAL-class storage. The S355 code
change improves convention compliance by routing user-facing persistence failures
through the centralized locale key and redacted structured context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/_runtime_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

`vaultspec-rag` evidence search could not run: service metadata reports stopped while
port 8766 is occupied, and the search process failed. I did not use in-process fallback
because the CLI warns that fallback can acquire the Qdrant lock and block other agents.
