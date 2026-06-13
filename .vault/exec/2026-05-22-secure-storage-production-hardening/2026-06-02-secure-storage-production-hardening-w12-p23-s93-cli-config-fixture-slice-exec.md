---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-cli-config-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` CLI Config Fixture Slice

## Description

- Remove redundant fixture-level `dispose_engine()` wrappers from CLI config tests already using `isolated_profile_storage_root`.
- Preserve intentional test-body engine flushes that force profile database corruption or multi-command state transitions to be observed.
- Keep the slice scoped away from manual application-layer bucket-session tests that require separate approved-route classification.

## Changed Surface

- `src/aeat/entrypoints/cli/_config/test_apoderado.py`
- `src/aeat/entrypoints/cli/_config/test_config.py`
- `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py`

## Outcome

Closed for this slice.

The three CLI config fixtures now rely on the centralized profile-storage helper for setup and teardown instead of wrapping it in local engine-disposal boilerplate. The tests still create real profile buckets, exercise real CLI commands, and assert persisted secure-object behavior.

## Verification

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/_config/test_config.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` - 14 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/_config/test_config.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/_config/test_config.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` - no matches.
- `git diff --check -- src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/_config/test_config.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. Remaining work includes approved-route classification, manual bucket-session tests, `test_modelo_export_verb.py`, profile lifecycle fixture cleanup, and guard/closeout rows S94-S95.
