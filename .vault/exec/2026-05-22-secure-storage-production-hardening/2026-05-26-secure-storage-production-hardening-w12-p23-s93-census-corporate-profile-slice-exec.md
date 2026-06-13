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



# `secure-storage-production-hardening` `W12.P23.S93` Census And Corporate Profile Slice

Moved another user-profile persistence slice from explicit database-route setup onto the sanctioned runtime-profile helper.

## Changes

- Replaced the census sync test fixture's manual `AEAT_DATABASE_URL`, injected engine, ORM table creation, and direct `SecureObjectRepository(engine=...)` setup with `isolated_runtime_profile`.
- Kept census tests on a distinct bucket/profile contract: runtime bucket `b1`, profile id `operator`.
- Replaced corporate-tax fact roundtrip setup with `isolated_runtime_profile` and a runtime-owned repository.
- Preserved corporate-tax bucket/profile separation: runtime and repository bucket id `corporate-tax-roundtrip`, persisted profile id `_PROFILE_UUID`.
- Replaced corporate-tax anti-tautology direct `SecureObjectRow` / `session_scope` mutation with runtime repository `load` / `save` payload mutation.

## Validation

- `uv run --no-sync pytest src/aeat/application/user_profile/test_census_sync.py src/aeat/application/user_profile/test_corporate_tax_facts_roundtrip.py -q` - 13 passed.
- `uv run --no-sync ruff check src/aeat/application/user_profile/test_census_sync.py src/aeat/application/user_profile/test_corporate_tax_facts_roundtrip.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|Base\.metadata|SecureObjectRow|session_scope\(|EphemeralMasterKeyProvider|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...census/corporate slice...` - no matches.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`, unrelated to this source slice.

## Review

The initial `vaultspec-code-reviewer` pass found one Medium issue: corporate-tax runtime bucket id had been collapsed to the persisted profile UUID, weakening route/id separation. The test now restores distinct bucket id `corporate-tax-roundtrip` while retaining `_PROFILE_UUID` as the record identity. Re-review found no findings.

S93 remains open because the plan row covers the broader `src/aeat` migration. S94 and S95 still need guard coverage and approved explicit-route inventory.
