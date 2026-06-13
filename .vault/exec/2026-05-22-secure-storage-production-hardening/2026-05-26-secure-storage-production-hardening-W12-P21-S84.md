---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S84'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S83]]'
  - '[[2026-05-26-active-profile-storage-runtime-classification-closeout-audit]]'
---



# `secure-storage-production-hardening` `W12.P21.S84`

Migrated S84 domain repositories to runtime-owned secure-object defaults while preserving explicit repository injection for callers that already own a storage handle.

## Changes

- Updated the shared `SecureBoundRepository` default path so filing drafts, submissions, and justificantes resolve storage through the active-profile runtime instead of constructing raw storage directly.
- Added lazy runtime resolution to `SecureBoundRepository`, so constructing a repository for path markers or identifier validation does not open storage before the method needs it.
- Moved usage-ratio default load/save paths onto the existing adapter-owned runtime repository factory.
- Preserved explicit `objects=` injection for real repositories used in tests and co-transactional application flows.
- Migrated intersecting usage-ratio census, justificante, filing amendment, and draft anti-tautology tests away from `AEAT_DATABASE_URL` and monkeypatch-based storage setup.
- Replaced the amendment anti-tautology broad exception assertion with a concrete `ValidationError` expectation.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/domain/usage_ratios/_service.py src/aeat/domain/usage_ratios/test_census_refuse_load.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/_complementaria_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/justificante/_repository.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/_repository.py src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/submission/_repository.py src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py`
- `uv run --no-sync pytest src/aeat/domain/usage_ratios/test_service.py src/aeat/domain/usage_ratios/test_census_refuse_load.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/justificante/test_secure_storage_roundtrip.py src/aeat/domain/submission/test_repository.py src/aeat/domain/submission/test_secure_storage_roundtrip.py -q`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_submission_repository.py -q`
- `rg -n "SecureObjectRepository\(|objects or SecureObjectRepository|AEAT_DATABASE_URL|monkeypatch|noqa|pragma" ...`
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

- The S84 production search found no remaining raw secure-object constructor defaults in the targeted repository files.
- The mandatory review raised one LOW layering concern about a domain-level runtime helper duplicating the adapter factory; S84 resolved it before closure by deleting that helper and importing the adapter-owned runtime factory directly.
- A broader domain lint run still reports unrelated pre-existing formatting issues outside the S84 write set.
- A broader domain pytest run passed `358` tests and failed one namespace-guard test because `repair_integrity.py` still references the work-unit namespace outside the canonical repository. That file is outside S84 and is already assigned to application migration work.
