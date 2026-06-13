---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-application-bootstrap-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` Application Bootstrap Slice

## Description

- Replace local application bootstrap test wrappers with the centralized `isolated_profile_storage_root` helper.
- Remove duplicated `SecretStoreBackend`, `dev_test_database_password`, and local `dispose_engine(settings)` setup from profile-create and workflow parity tests.
- Preserve intentional per-invocation cold-start engine disposal where the tested CLI behavior depends on process-reload semantics.
- Preserve teardown-only global engine cleanup where the test opens an active-profile route after the shared profile-storage helper enters.

## Changed Surface

- `src/aeat/application/test_config_parity.py`
- `src/aeat/application/test_cli_workflow_verification.py`
- `src/aeat/application/setup/test_service_provisions_bucket.py`
- `src/aeat/application/setup/test_atomic_create_rollback.py`
- `src/aeat/application/setup/test_atomic_create_roundtrip.py`

## Outcome

Closed for this slice.

The five application bootstrap tests now use the shared profile-storage isolation helper for empty profile-bootstrap storage roots and file-backed custody setup. The slice removes local settings wrangling and settings-bound duplicated engine disposal while retaining real profile creation, bucket provisioning, rollback, import/export, and workflow parity behavior.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/test_config_parity.py src/aeat/application/test_cli_workflow_verification.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py` - 16 passed.
- `uv run --no-sync ruff check src/aeat/application/test_config_parity.py src/aeat/application/test_cli_workflow_verification.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|dispose_engine\\(settings\\)|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/application/test_config_parity.py src/aeat/application/test_cli_workflow_verification.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py` - no matches.
- `git diff --check -- src/aeat/application/test_config_parity.py src/aeat/application/test_cli_workflow_verification.py src/aeat/application/setup/test_service_provisions_bucket.py src/aeat/application/setup/test_atomic_create_rollback.py src/aeat/application/setup/test_atomic_create_roundtrip.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. This slice deliberately leaves `_invoke()` in `test_atomic_create_roundtrip.py` calling `dispose_engine()` before each CLI verb because the test asserts cold-start consistency across command invocations, not fixture isolation. The review also retained a teardown-only global `dispose_engine()` in `test_cli_workflow_verification.py` because `profile_create_storage_span("operator")` opens an active-profile route after the shared helper enters, and Windows cleanup needs that active-profile engine closed.
