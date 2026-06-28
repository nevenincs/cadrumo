---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S358'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S358 - Close AFR-256 for modelo verification reports

Scope: close `AFR-256` for `src/aeat/domain/modelos/_verification_repository.py`
with signals `secure-object, manifest-bucket`, target `runtime-default`, and owner
`W12.P21.S84`.

## Description

- Audited `VerificationReportCatalogueRepository` default construction and confirmed
  it resolves buckets through `resolve_modelo_repository_bucket_id` and obtains secure
  objects through the runtime-owned modelo helper.
- Confirmed verification reports persist as FINANCIAL envelopes under the stable
  `aeat.domain.modelos.verification_reports` namespace and singleton catalogue key.
- Hardened load-time integrity failures to raise
  `errors.fail.fail_modelo_verification_report_persistence` with structured context
  instead of interpolating raw secure-storage exception text into the operator-facing
  error.
- Added real encrypted-storage tests for corrupted inner envelope classification and
  unsupported inner envelope schema versions.
- Closed `W12.P26.S358` through `vaultspec-core vault plan step check` and updated
  the `AFR-256` register status to `closed`.

## Outcome

`AFR-256` is closed as `runtime-default`. Verification-report persistence remains
bucket-scoped, runtime-created, encrypted, FINANCIAL-class storage. The S358 change
aligns its failure contract with the calculation, filing-record, and work-unit
catalogues.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/modelos/test_verification_report_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`

## Notes

No locale file edits were required for S358 because
`errors.fail.fail_modelo_verification_report_persistence` already exists and the
locale audit stayed clean in the shared worktree.
