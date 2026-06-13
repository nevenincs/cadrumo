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



# `secure-storage-production-hardening` `W12.P23.S93` Profile Bootstrap Helper Slice

Centralized the profile-bootstrap storage-root setup used by profile creation and lifecycle route tests without pre-provisioning a profile bucket.

## Changes

- Added `isolated_profile_storage_root`, a shared secure-SQL test helper that provides an isolated storage root and active test key session while leaving profile bucket creation to the system under test.
- Moved `ProfileRepository` cross-store tests from inline `EphemeralMasterKeyProvider`, settings override, and engine-disposal setup onto the shared helper.
- Moved lifecycle repository default-route tests onto the shared helper while preserving the explicit database URL refusal assertion.
- Kept the refusal test's physical side-effect checks: neither the explicit database file nor the target bucket database may be created after rejection.

## Validation

- `uv run pytest src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/user_profile/test_repository.py -q` - 25 passed.
- `uv run ruff check src/aeat/tests/secure_sql.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/user_profile/test_repository.py` - passed.
- `rg -n "EphemeralMasterKeyProvider|aeat_database_url|sqlite:///|except Exception|noqa|pragma|monkeypatch|config init" ...profile bootstrap slice...` - expected hits only in the shared secure-SQL helpers and the explicit database URL refusal test.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`; this metadata defect is tracked but is not an execution blocker for this source slice.

## Review

The `vaultspec-code-reviewer` pass found no findings. The reviewer confirmed the helper does not pre-provision a bucket, manifest, pointer, or per-bucket database, and that the explicit database URL refusal coverage remains meaningful.

S93 remains open because the row covers the broader `src/aeat` migration. The next execution increments should continue separating helper-eligible storage setup from explicit route/refusal tests that belong in the approved S95 inventory.
