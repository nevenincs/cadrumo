---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-output-work-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` Output Work Fixture Slice

## Description

- Remove redundant fixture-level `dispose_engine()` wrappers from output-language and work-resume tests already using `isolated_profile_storage_root`.
- Preserve real profile bootstrap via `profile_create_storage_span`.
- Exclude repair privacy contract cleanup after its focused test file exposed a diagnostics model-rebuild failure during this shared-worktree run, unrelated to this fixture edit.

## Changed Surface

- `src/aeat/tests/test_output_language.py`
- `src/aeat/entrypoints/cli/test_work_resume.py`

## Outcome

Closed for this slice.

The two fixtures now rely on the centralized profile-storage helper for setup and teardown instead of local engine-disposal boilerplate. The tests still exercise profile-owned locale resolution and real CLI work-resume persistence through the profile bucket runtime.

## Verification

- `uv run --no-sync pytest -q src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/test_work_resume.py` - 14 passed.
- `uv run --no-sync ruff check src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/test_work_resume.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|dispose_engine\\(|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/test_work_resume.py` - no matches.
- `git diff --check -- src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/test_work_resume.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` - no whitespace errors.

## Notes

`src/aeat/entrypoints/cli/test_repair_privacy_contract.py` was intentionally excluded. Its fixture cleanup was attempted and then reverted after the focused file failed during this shared-worktree run through `SecureObjectNamespaceIntegrity` being unavailable during diagnostics Pydantic model rebuild. That surface requires separate grounding before the file can be migrated or classified.

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. Remaining work includes approved-route classification, repair privacy diagnostics follow-up, manual bucket-session tests, `test_modelo_export_verb.py`, profile lifecycle fixture cleanup, and guard/closeout rows S94-S95.
