---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S16'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
---



# `secure-storage-production-hardening` `W02.P04.S16`

Enrolled the modelo work-unit, calculation, filing-record, verification-report, filing-draft, amendment, and filing-history repository defaults in runtime-created, bucket-attached secure storage while preserving explicit secure-object injection.

## Changes

- Added a shared runtime secure-object repository factory that resolves bucket-attached storage through the storage runtime.
- Added modelo, domain filing, and application filing runtime helpers that resolve the requested bucket or active bucket and raise typed application/domain errors when no bucket is active.
- Added optional `bucket_id` support to the touched repository constructors and exposed the resolved bucket for runtime-binding assertions.
- Preserved explicit `objects` injection for real-behavior tests and controlled callers while removing unqualified production fallback construction from the touched defaults.
- Regrounded the touched modelo and filing roundtrip tests on real `BucketSession` activation and `override_settings` root/profile routing rather than patched database environment variables.
- Updated encrypted-database assertions to inspect the runtime bucket database path.
- Removed the complementaria test's remaining patched database environment route and regrounded work-unit secure-storage tests on default runtime bucket construction.

## Validation

- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/domain/modelos/_runtime_repository.py src/aeat/domain/filing/_runtime_repository.py src/aeat/application/filing/_runtime_repository.py src/aeat/domain/modelos/_repository.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/filing/_complementaria_repository.py src/aeat/application/filing/_history_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/application/filing/conftest.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run pytest src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_complementaria_repository.py -q`
- `uv run pytest src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_complementaria_repository.py -q`
- `uv run python -m aeat.locales audit`
- `rg 'AEAT_DATABASE_URL|EphemeralMasterKeyProvider|Base\.metadata|monkeypatch|tmp_path / "aeat\.db"' src/aeat/application/filing src/aeat/domain/filing src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py -n`
- `rg 'AEAT_DATABASE_URL|EphemeralMasterKeyProvider|Base\.metadata|monkeypatch|tmp_path / "aeat\.db"|aeat_database_url' src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/conftest.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_secure_storage_roundtrip.py -n`

## Review

The touched S16 repository defaults now resolve through active-profile storage runtime before constructing secure-object repositories. The mandatory S16 review raised two medium test-surface findings; both were resolved before closeout and documented in `2026-05-26-secure-storage-production-hardening-W02-P04-S16-review-audit`.
