---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Residual Guard Inventory

W15.P32 records the approved residual storage-surface exceptions after hardening the executable guards.

## Approved Residuals

- `src/aeat/tests/test_config.py` may still mutate/read `AEAT_*` variables because it is the Settings boundary contract test.
- `src/aeat/core/test_token_dir_state_root.py` may still exercise `AEAT_TOKEN_DIR` and `AEAT_LOCAL_STORAGE_ROOT` because it verifies settings-derived path precedence.
- `src/aeat/core/observability/test_*.py` may still set `AEAT_RUNS_DIR` while the observability tests are migrated to `override_settings`.
- `src/aeat/entrypoints/cli/conftest.py` and explicit CLI guard tests may still pass `env={...}` into real CLI invocations when the test's subject is CLI environment ingestion or refusal.
- `src/aeat/adapters/outbound/**/test_*_live.py` may still read live opt-in gates directly until live-test gating is centralized under Settings.
- Low-level SQL substrate tests under `src/aeat/adapters/persistence/storage/sql/` may still construct explicit `Settings(aeat_database_url=...)` routes because the SQL engine/session/repository layer is their direct subject.

## Guarded Outcomes

- Production `SecureObjectRepository` construction is now constrained to runtime-owned factories.
- Active bucket route derivation uses `settings_for_active_profile_bucket` in `core.config`; storage runtime no longer rewrites pydantic field metadata itself.
- Repair diagnostics and repair integrity builders resolve repositories through runtime helpers instead of constructing the default SQL repository directly.
- Repair list, quarantine preview, and quarantine mutation enter the active-bucket repair session helper before resolving active-bucket repositories, covering the bootstrap-exempt repair command path.
- Secure-bound envelope repositories use the runtime repository helper and no longer swallow active-bucket route/session failures by falling back to a bare repository.
- Database-backed tests that use ephemeral master keys must carry explicit isolation through settings and engine disposal, or inject repositories directly.
- Database-backed tests must not carry literal passphrase callbacks, literal `AEAT_SECRET_PASSPHRASE`, or literal `aeat_secret_passphrase` overrides.

## Follow-Up

W15.P33 should promote the remaining namespace/object-key/storage hierarchy values into a typed registry before more call sites are migrated. The residual environment-test list above should be retired incrementally as Settings-backed helpers are added for CLI, observability, live-test gating, and token-directory scenarios.
