---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `settings and environment handling`

## Scope

Audited storage-route and secure-storage-adjacent environment handling for centralized `Settings`, `load_settings`, and `override_settings` usage.

## Good Patterns

- `src/aeat/core/config.py` is the canonical source for AEAT env definitions and storage-route classification.
- `load_settings()` and `override_settings()` provide a process-local settings boundary for application and test code.
- `src/aeat/adapters/persistence/storage/runtime.py` routes named-bucket runtime inspection through `Settings` objects and keeps explicit `aeat_database_url` routes fail-closed.
- `src/aeat/tests/secure_sql.py` provides `isolated_ephemeral_secure_sql(...)`, a reusable settings-backed test helper.
- Production direct `os.environ` access is limited to non-AEAT or explicitly core-owned cases: CLI `COLUMNS`, observability replay process state, Windows file-permission probes, i18n env cache signatures, and test access-gate context.

## Findings

- High: storage-adjacent tests still mutate `AEAT_DATABASE_URL`, `AEAT_LOCAL_STORAGE_ROOT`, and related AEAT env vars through `monkeypatch` or direct `os.environ`. This appears across CLI, application, domain, and storage tests. Env parser tests are a legitimate exception; repository and workflow tests should use settings-backed helpers.
- High: `override_settings()` merges `current.model_dump()` with overrides. When callers override `aeat_local_storage_root` or `aeat_active_profile` without an explicit `aeat_database_url`, the merged dump may retain a stale derived database URL from the prior settings object. Current runtime code works around this in named-bucket inspection; the core settings helper should own that re-derivation rule.
- Medium: some production messages and comments still instruct operators to set `AEAT_DATABASE_URL` directly. S65 already assigns user-facing wording cleanup; S69 confirms the same problem from the settings-centralization perspective.
- Medium: test fixtures that set `AEAT_SECRET_STORE_BACKEND=unsecured` and `AEAT_ALLOW_UNENCRYPTED=1` should be reviewed alongside secure-storage runtime readiness. Where a real unlocked ephemeral bucket session can satisfy the behavior, that path is preferred over unsecured env gating.
- Low: direct `os.environ` in `src/aeat/core/access_gate` is documented as an intentional live-test gate exception. It should stay core-owned and not be copied into application or adapter code.

## Disposition

- `W11.P19.S74` owns `override_settings()` re-derivation hardening and migration of storage-adjacent tests to centralized settings helpers.
- `W11.P19.S77` owns guard expansion for new naked AEAT env access outside config/env-loader/test-gate exceptions.
- `W11.P18.S71` owns user-facing wording that currently points operators at direct env mutation.

## Validation

The audit used targeted `rg` scans for `os.environ`, `os.getenv`, `getenv`, `monkeypatch.setenv`, `monkeypatch.delenv`, `Settings`, `load_settings`, and `override_settings` across core, storage, application, domain, CLI, and tests.
