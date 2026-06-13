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



# `secure-storage-production-hardening` `W12.P23.S93` Profile Health Slice

Moved active-profile health and repair tests from manual bucket-session setup onto the sanctioned runtime-profile helper.

## Changes

- Replaced explicit `EphemeralMasterKeyProvider`, `BucketSession`, `activate_session`, and `dispose_engine` setup with `isolated_runtime_profile`.
- Kept missing-profile tests on a real manifest plus pointer route while leaving the encrypted profile row absent.
- Seeded healthy profile records through `UserProfileLifecycleRepository` and the runtime-created repository, avoiding a second profile-create path over the helper manifest.
- Preserved pointer-route coverage by clearing `aeat_active_profile` and asserting `health.source == "pointer"` for the healthy-pointer repair test.
- Removed direct manifest staging helper and hard-coded KDF/session fixtures from the test file.

## Validation

- `uv run --no-sync pytest src/aeat/application/workflow/test_profile_health.py -q` - 4 passed.
- `uv run --no-sync ruff check src/aeat/application/workflow/test_profile_health.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|Base\.metadata|SecureObjectRow|session_scope\(|EphemeralMasterKeyProvider|activate_session|BucketSession|dispose_engine|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...profile health slice...` - no matches.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`, unrelated to this source slice.

## Review

The initial `vaultspec-code-reviewer` pass found one Medium issue: the healthy-pointer repair test was accidentally exercising the helper's `env_override` route instead of the pointer route. The test now clears `aeat_active_profile` around the health and repair calls and asserts `health.source == "pointer"`. Re-review found no findings.

S93 remains open because the plan row covers the broader `src/aeat` migration. S94 and S95 still need guard coverage and approved explicit-route inventory.
