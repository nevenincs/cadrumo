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



# `secure-storage-production-hardening` `W12.P23.S93` User Profile Repository Slice

Closed a focused user-profile repository increment after concurrent cross-campaign work migrated the main repository fixtures to the sanctioned runtime profile helper.

## Changes

- Confirmed the user-profile repository tests now use runtime-created secure-object repositories for the migrated roundtrip and anti-tautology surfaces.
- Tightened snapshot roundtrip tests so the injected runtime repository remains the physical test store while the logical repository id is the immutable profile UUID.
- Updated snapshot anti-tautology mutation paths to use `user-profile-snapshot:{uuid}:{snapshot_id}` rather than the helper's physical runtime bucket id.
- Removed stale docstring references to direct `SecureObjectRow` and `session_scope` mutation from user-profile anti-tautology tests.
- Preserved the explicit `aeat_database_url` refusal test as approved route-policy coverage.

## Validation

- `uv run --no-sync pytest src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/application/user_profile/test_repository_anti_tautology.py -q` - 14 passed.
- `uv run --no-sync ruff check src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/application/user_profile/test_repository_anti_tautology.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|Base\.metadata|SecureObjectRow|session_scope\(|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...user-profile repository slice...` - one approved explicit-route refusal hit in `test_default_lifecycle_repository_refuses_explicit_database_url`.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`, unrelated to this source slice.

## Review

The initial `vaultspec-code-reviewer` pass found one Medium route-fidelity issue: the snapshot anti-tautology mutation used the physical runtime helper bucket id instead of the logical UUID profile id. The test now constructs the lifecycle and snapshot repositories with `_PROFILE_UUID` and mutates `user_profile_snapshot_object_key(_PROFILE_UUID, snapshot_id)`. Re-review found no findings.

S93 remains open because the plan row covers the broader `src/aeat` migration. S94 and S95 still need guard coverage and approved explicit-route inventory.
