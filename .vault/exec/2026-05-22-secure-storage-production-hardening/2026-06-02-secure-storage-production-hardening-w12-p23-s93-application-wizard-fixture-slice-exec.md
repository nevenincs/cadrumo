---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-application-wizard-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` Application Wizard Fixture Slice

## Description

- Replace local file-backed custody setup and local engine-disposal wrappers with `isolated_profile_storage_root`.
- Preserve real profile creation spans, workflow-state persistence, wizard command execution, and pointer atomicity assertions.
- Retain the pointer-atomicity test-body `dispose_engine()` call that deliberately flushes state before the duplicate-create refusal path.

## Changed Surface

- `src/aeat/application/test_config_reset.py`
- `src/aeat/application/wizard/test_commands.py`
- `src/aeat/application/wizard/test_create_pointer_atomicity.py`
- `src/aeat/application/wizard/test_status.py`

## Outcome

Closed for this slice.

The four fixtures now use the centralized profile-storage helper for the file-backed custody path instead of repeating `SecretStoreBackend.FILE`, dev-test passphrase, storage-root, and settings-bound engine cleanup setup locally.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/test_config_reset.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_create_pointer_atomicity.py` - 16 passed.
- `uv run --no-sync ruff check src/aeat/application/test_config_reset.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_create_pointer_atomicity.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/application/test_config_reset.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_create_pointer_atomicity.py` - no matches.
- `git diff --check -- src/aeat/application/test_config_reset.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_create_pointer_atomicity.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. Remaining work includes approved-route classification, repair privacy diagnostics follow-up, manual bucket-session tests, `test_modelo_export_verb.py`, profile lifecycle fixture cleanup, auth-session provider test-double classification, and guard/closeout rows S94-S95.
