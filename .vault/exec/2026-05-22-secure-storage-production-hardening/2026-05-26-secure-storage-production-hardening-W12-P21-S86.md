---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S86'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S85]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p21-s86-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P21.S86`

Migrated outbound, profile, attachment, and secure-bound adapter defaults away from deprecated process database routes and onto active profile-bucket runtime ownership.

## Changes

- Routed AEAT browser-session, Google OAuth/session, LLM usage/cache, filed-observation, profile asset/inventory, attachment, and secure-bound repository defaults through active profile-bucket runtime factories or explicit injected repositories.
- Removed synthetic `ephemeral`/`unsecured` bucket bypasses from runtime readiness and SQL route matching; live repository construction now requires the active session bucket to match the active bucket database route.
- Made secure-object session freshness route-check by default so read/list/metadata APIs reject mismatched SQL routes with the same guard as writes.
- Removed the `EphemeralMasterKeyProvider` no-active-profile fallback to synthetic `ephemeral`; entering the provider now requires an active bucket.
- Exported the runtime-owned secure-object repository factories from the storage package public API.
- Replaced the filed-observation store's custom synthetic session with the canonical master-key provider context so provider-backed writes use the same active bucket session semantics as the rest of secure storage.
- Migrated S86 adapter tests and contract suites off `AEAT_DATABASE_URL`, explicit `Settings(aeat_database_url=...)`, and raw default `SecureObjectRepository()` setup; tests now use `override_settings` with `aeat_local_storage_root`, `aeat_active_profile`, and real active bucket sessions.
- Removed suppressive coverage pragmas from LLM storage-path exception handling and kept exception paths logged or surfaced through typed boundary errors.

## Validation

- `uv run --no-sync ruff check` over the S86 production and test file set passed.
- `uv run --no-sync pytest ... -q` over the S86 focused storage/auth/observation/profile/envelope/runtime gate passed with 80 tests.
- `rg -n 'AEAT_DATABASE_URL|Settings\(aeat_database_url|SecureObjectRepository\(\)|bucket_id="ephemeral"|filed-declaration-store' ...` returned no matches in the S86 adapter/profile/envelope scope.
- `rg -n 'noqa|pragma: no cover|type: ignore' ...` returned no matches in the S86 production/runtime/envelope storage scope.

## Notes

- A full `test_declarations.py` run still reports three Modelo 303 parser/layout failures unrelated to secure-storage routing. The two filed-observation encrypted storage tests in that file pass under the new active bucket fixture.
- Broad Playwright-facing cleanup catches remain in `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`; they log warning/debug context and preserve original auth failures rather than silently swallowing storage defects.
