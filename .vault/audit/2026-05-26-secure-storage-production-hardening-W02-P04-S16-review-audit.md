---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W02-P04-S15]]'
---



# `secure-storage-production-hardening-W02-P04-S16` Code Review



S16-001 | MEDIUM | Touched complementaria test still relies on env/monkeypatch database routing
`src/aeat/application/filing/test_complementaria.py:28` defines a module autouse fixture with `monkeypatch`, and `src/aeat/application/filing/test_complementaria.py:39` sets `AEAT_DATABASE_URL` directly. That is a touched test surface and conflicts with the S16/S15 route discipline that moved repository defaults to `override_settings(aeat_local_storage_root=...)` plus an active `BucketSession`. Because the package conftest already installs active-bucket runtime setup, this extra fixture can mask whether complementaria flows are using the runtime-created bucket store and violates the explicit no env/monkeypatch shortcut rule for touched tests.

S16-002 | MEDIUM | Work-unit roundtrip still bypasses runtime-created repository enrollment
`src/aeat/domain/modelos/test_secure_storage_roundtrip.py:101` and `src/aeat/domain/modelos/test_secure_storage_roundtrip.py:178` construct explicit `Settings(aeat_database_url=...)`, then `src/aeat/domain/modelos/test_secure_storage_roundtrip.py:111` and `src/aeat/domain/modelos/test_secure_storage_roundtrip.py:186` inject `SecureObjectRepository` into `WorkUnitCatalogueRepository`. That preserves a valid injection path, but it does not prove the S16 plan item for modelo work-unit repositories: runtime-created secure storage and bucket DB binding through `WorkUnitCatalogueRepository(bucket_id=...)`. The other S16 filing/modelo roundtrip tests exercise `override_settings(aeat_local_storage_root=...)`, `BucketSession`, and repository default construction; the work-unit repository remains the outlier.

## Verification

- `uv run pytest src/aeat/application/filing/test_complementaria.py -q`
- `uv run pytest src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_history_repository_roundtrip.py -q`
- `uv run pytest src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/application/filing/test_history_repository.py -q`
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/domain/modelos/_runtime_repository.py src/aeat/domain/filing/_runtime_repository.py src/aeat/application/filing/_runtime_repository.py src/aeat/domain/modelos/_repository.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/filing/_complementaria_repository.py src/aeat/application/filing/_history_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/filing/conftest.py src/aeat/application/filing/test_complementaria.py`
- `uv run python -m aeat.locales audit`

## Residual Risks

No production runtime bucket-binding failure was observed in the scoped repository constructors: default construction routes through `secure_object_repository_for_bucket`, and runtime readiness rejects mismatched active sessions. The remaining risk is test-surface drift: explicit object injection remains valid for controlled tests, so coverage must include at least one default-construction path for each enrolled repository family.

## Resolution

S16-001 | RESOLVED | Replaced the complementaria test's module-level database env fixture and draft/submission env helper with the package active-bucket runtime. Negative complementaria cases now assert the runtime amendment repository remains empty rather than inspecting a plaintext submissions directory.

S16-002 | RESOLVED | Regrounded the work-unit secure-storage roundtrip and anti-tautology proof on `override_settings(aeat_local_storage_root=...)`, `BucketSession`, and `WorkUnitCatalogueRepository(bucket_id=...)`. The roundtrip test now asserts the resolved bucket id and runtime bucket database path.

Resolution validation:

- `uv run ruff check src/aeat/application/filing/test_complementaria.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py`
- `uv run pytest src/aeat/application/filing/test_complementaria.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py -q`
- `uv run pytest src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_complementaria_repository.py -q`
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/domain/modelos/_runtime_repository.py src/aeat/domain/filing/_runtime_repository.py src/aeat/application/filing/_runtime_repository.py src/aeat/domain/modelos/_repository.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/filing/_complementaria_repository.py src/aeat/application/filing/_history_repository.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/application/filing/conftest.py src/aeat/application/filing/test_complementaria.py src/aeat/application/filing/test_repository.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run python -m aeat.locales audit`
