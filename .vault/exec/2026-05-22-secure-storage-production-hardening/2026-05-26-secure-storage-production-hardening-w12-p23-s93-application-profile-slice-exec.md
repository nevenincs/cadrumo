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



# `secure-storage-production-hardening` `W12.P23.S93` Application Profile Slice

Moved a focused application workflow and user-profile persistence slice from ad hoc SQL/key-provider setup onto the sanctioned runtime-profile helper.

## Changes

- Replaced the active transaction catalogue resolution fixture's manual `Settings(aeat_database_url=...)`, injected engine, ORM table creation, and direct `SecureObjectRepository(engine=...)` setup with `isolated_runtime_profile`.
- Replaced the user-profile lifecycle service fixture's manual explicit-database setup with a runtime-created repository.
- Replaced user-profile orchestration and pointer-file fixtures with runtime-created repositories while clearing `aeat_active_profile` inside the fixture so the tests still prove pointer-file resolution.
- Replaced taxpayer-axis encrypted persistence fixtures with a runtime-created repository and retained the real pointer-selected active-profile behavior under `override_settings(aeat_active_profile=None)`.
- Removed stale docstring references to manual ephemeral key provider and explicit SQLite setup from the migrated taxpayer-axis test.

## Validation

- `uv run --no-sync pytest src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/application/user_profile/test_lifecycle.py src/aeat/application/user_profile/test_orchestration.py src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/application/user_profile/test_taxpayer_axes_persistence_roundtrip.py -q` - 24 passed.
- `uv run --no-sync ruff check src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/application/user_profile/test_lifecycle.py src/aeat/application/user_profile/test_orchestration.py src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/application/user_profile/test_taxpayer_axes_persistence_roundtrip.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|EphemeralMasterKeyProvider|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...application profile slice...` - no matches.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`, unrelated to this source slice.

## Review

The `vaultspec-code-reviewer` review found no issues. The reviewer confirmed the migration preserves real behavior through `isolated_runtime_profile`, keeps pointer assertions on the real pointer-file path, uses runtime-created repositories, and does not introduce hidden exception handling, pragma/noqa suppressions, fakes, stubs, skips, xfails, or tautological tests.

S93 remains open because the plan row covers the broader `src/aeat` migration. S94 and S95 still need the guard coverage and approved explicit-route inventory.
