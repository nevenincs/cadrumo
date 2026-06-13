---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S89'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p22-s89-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P22.S89`

Moved profile lifecycle storage spans for create, switch, delete, and logout behind named application-layer operations while keeping `ProfileRepository` as the cross-store writer.

## Changes

- Added application-owned profile lifecycle storage operations for create custody, existing-profile session activation, switch/activation, delete/tombstone, and logout pointer clearing.
- Moved wizard create/edit persistence and setup service initialization onto those lifecycle operations instead of importing master-key providers or writing active-profile pointers directly.
- Reduced CLI profile create/import/duplicate, switch, delete, and logout surfaces to transport-level orchestration that delegates storage spans to application user-profile operations.
- Moved `PROFILE_ACTIVATED` bucket-event persistence out of the CLI and into application user-profile orchestration.
- Extended `ProfileRepository.create` with an explicit bootstrap routing profile id so the temporary route state used for cold-start creation is restored and the active pointer is written inside the repository before the encrypted record commit.
- Updated setup CLI smoke tests from explicit database/unsecured storage to real file-backed profile-bucket custody.
- Added focused real-entrypoint coverage proving profile create provisions file custody, writes bucket-DEK metadata, logout clears the active pointer, switch reopens the bucket, delete tombstones through the lifecycle span, and retired `config init` remains absent.
- Added a static ownership guard proving CLI, wizard, and setup-service lifecycle surfaces do not own direct master-key provider activation, active-profile pointer writes, active-profile override spans, direct repository delete calls, or CLI-local activation event writes.

## Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_profile_repository.py src/aeat/application/user_profile/_orchestration.py src/aeat/application/wizard/_persistence.py src/aeat/application/wizard/_commands.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/application/setup/_service.py src/aeat/application/setup/test_cli.py src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py` - passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/application/setup/test_cli.py src/aeat/application/user_profile/test_profile_repository.py -q` - 23 passed.
- `uv run --no-sync pytest src/aeat/application/test_storage_write_policy.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py -q` - 59 passed.
- `rg -n "activate_master_key_provider|get_master_key_provider|_write_active_profile_pointer|_clear_active_profile_pointer|capture_active_profile_pointer|restore_active_profile_pointer|override_settings\\(aeat_active_profile|ProfileRepository\\(\\)\\.delete|BucketEventHistoryRepository\\(\\)" src/aeat/application/wizard/_commands.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/application/setup/_service.py` - only a read-only bucket-history load command remains outside the lifecycle surfaces.
- `rg -n "cli\\.config\\.init|aeat config init|config init" src/aeat/application/user_profile/_orchestration.py src/aeat/application/wizard/_commands.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/application/setup/_service.py src/aeat/application/setup/test_cli.py src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml` - only the explicit regression-test docstring asserting the retired command is not reintroduced.

## Review

The mandatory review found one high and two medium issues: create still wrote a pointer outside `ProfileRepository`, delete still assembled its lifecycle span in the CLI, and switch still persisted `PROFILE_ACTIVATED` from the CLI. Remediation moved those responsibilities into repository/application user-profile orchestration, and narrow re-review passed.

## Follow-Up

Broader legacy profile lifecycle suites still contain older fixtures that seed workflow state without an active profile or force unsecured/explicit database routes. Those are not accepted hardened runtime setup patterns and should be migrated under the later test-runtime/profile-boundary rows rather than weakening S89's production lifecycle boundary.
