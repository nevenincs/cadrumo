---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S60'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W07.P14.S60`

## Description

- Repair the next bounded residual secure-SQL hygiene slice selected by S59.
- Remove bespoke passphrase/file-backend setup from the application/modelo test fixture cluster.
- Preserve real profile and bucket behavior without fakes, stubs, monkeypatches, private taxpayer data, or root-database cross-contamination.

## Changed Surface

- `src/aeat/application/modelo/test_export.py`
- `src/aeat/application/modelo/test_reconcile.py`

## Outcome

Closed.

`test_export.py` now routes its operator-profile setup through `isolated_profile_storage_root(tmp_path=tmp_path)` while retaining the real profile-create storage span opened by `_ensure_operator_storage_span`.

`test_reconcile.py` now routes its real profile bootstrap through `isolated_profile_storage_root(tmp_path=tmp_path)` plus `profile_create_storage_span("operator")`.

The repaired tests no longer configure `SecretStoreBackend.FILE`, `SecretStr`, `aeat_secret_passphrase`, or `dev_test_database_password()` directly. The repaired slice uses the centralized secure-SQL helper instead of naked environment or bespoke passphrase setup.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_reconcile.py` - 18 passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` - 2 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_reconcile.py src/aeat/tests/test_secure_sql.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` - all checks passed.
- `rg -n "SecretStr|SecretStoreBackend|dev_test_database_password|aeat_secret_passphrase|aeat_secret_store_backend|AEAT_DATABASE_URL|AEAT_SECRET_PASSPHRASE|monkeypatch|MonkeyPatch|setenv|os\\.environ|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|\\bskip\\b|\\bxfail\\b|_Fake|_Stub|mock|patch|unittest\\.mock" src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_reconcile.py -S` - no matches.

## Notes

No HIGH or CRITICAL issue was identified in this repair step.

Remaining residual classes from S59 remain open for later rows: profile bootstrap/import orchestration, no-active-profile refusal tests, explicit database-route refusal tests, and the non-isolation domain digest/import-order follow-ups.
