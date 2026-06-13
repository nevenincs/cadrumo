---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-cli-modelo-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` CLI Modelo Fixture Slice

## Description

- Remove redundant fixture-level engine disposal from CLI tests already using `isolated_profile_storage_root`.
- Keep real profile bootstrap, real CLI invocation, and real repository assertions.
- Exclude `test_modelo_export_verb.py` after targeted validation showed its disposal pattern is not yet proven redundant.

## Changed Surface

- `src/aeat/entrypoints/cli/test_config_setter.py`
- `src/aeat/entrypoints/cli/test_audit_verbs.py`
- `src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py`
- `src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py`
- `src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py`

## Outcome

Closed for this slice.

The five CLI fixtures now rely on the centralized profile-storage helper for entry and teardown isolation instead of wrapping it in redundant local `dispose_engine()` calls. `test_modelo_export_verb.py` remains outside this slice because removing its disposal exposed a real command-path failure, so it needs separate grounding before migration.

## Verification

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py` - 34 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|dispose_engine\\(|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py` - no matches.
- `git diff --check -- src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_audit_verbs.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_from_justificante_verb.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. The modelo export fixture was intentionally left for a later slice after the attempted migration failed one real CLI export test with an application startup registration error.
