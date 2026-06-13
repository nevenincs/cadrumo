---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P23.S93` Submission Slice

Started the broad S93 migration by moving one storage-owned repository test slice from explicit database-route setup onto the S92 runtime-profile helper.

## Changes

- Replaced the autouse `AEAT_DATABASE_URL` monkeypatch and manual ephemeral secret/blob backend setup with `isolated_runtime_profile`.
- Kept repository tests using production `SubmissionRepository` behavior and the default runtime-owned secure-object repository path.
- Updated the encrypted-payload assertion to inspect the active profile bucket database instead of a root-level test database.
- Left the foreign-class refusal test as a real secure-object row insertion through the active runtime, preserving the classification-gate proof.

## Validation

- `uv run --no-sync pytest -q src\aeat\adapters\persistence\storage\test_submission_repository.py src\aeat\tests\test_secure_sql.py` - 22 passed.
- `uv run --no-sync ruff check src\aeat\adapters\persistence\storage\test_submission_repository.py src\aeat\tests\secure_sql.py src\aeat\tests\test_secure_sql.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(" ...test_submission_repository.py` - only the intentional default `SecureObjectRepository()` classification-seeding call remains.

## Remaining

S93 remains open. The same migration policy still needs to be applied to other non-refusal tests that use explicit database URLs, environment-route monkeypatching, or injected engines.
