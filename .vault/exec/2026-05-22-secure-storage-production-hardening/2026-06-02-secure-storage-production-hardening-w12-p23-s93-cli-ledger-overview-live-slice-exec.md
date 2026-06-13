---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-cli-ledger-overview-live-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` CLI Ledger Overview Live Slice

## Description

- Remove redundant fixture-level `dispose_engine()` wrappers from CLI tests already using `isolated_profile_storage_root`.
- Preserve real profile bootstrap, real Typer CLI execution, live-read gate settings, and profile-censo snapshot assertions.
- Keep the slice scoped away from `test_modelo_export_verb.py`, whose disposal dependency needs separate grounding.

## Changed Surface

- `src/aeat/entrypoints/cli/test_ledger_bulk_classify.py`
- `src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py`
- `src/aeat/entrypoints/cli/test_ledger_preflight_verb.py`
- `src/aeat/entrypoints/cli/test_live_notifications_verbs.py`
- `src/aeat/entrypoints/cli/test_live_read_subgroups.py`
- `src/aeat/entrypoints/cli/test_overview_agenda_verb.py`
- `src/aeat/entrypoints/cli/test_overview_backlog_verb.py`
- `src/aeat/entrypoints/cli/test_overview_calendar_verb.py`
- `src/aeat/entrypoints/cli/test_overview_explain_verb.py`
- `src/aeat/entrypoints/cli/test_profile_censo_verbs.py`

## Outcome

Closed for this slice.

The ten CLI fixtures now rely on the centralized profile-storage helper for setup and teardown instead of wrapping it in local engine-disposal boilerplate. The tests still create real workflow profiles, exercise real CLI verbs, and assert persisted secure-object behavior.

## Verification

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_overview_agenda_verb.py src/aeat/entrypoints/cli/test_overview_backlog_verb.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_overview_explain_verb.py src/aeat/entrypoints/cli/test_profile_censo_verbs.py` - 80 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_overview_agenda_verb.py src/aeat/entrypoints/cli/test_overview_backlog_verb.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_overview_explain_verb.py src/aeat/entrypoints/cli/test_profile_censo_verbs.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|dispose_engine\\(|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_overview_agenda_verb.py src/aeat/entrypoints/cli/test_overview_backlog_verb.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_overview_explain_verb.py src/aeat/entrypoints/cli/test_profile_censo_verbs.py` - no matches.
- `git diff --check -- src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py src/aeat/entrypoints/cli/test_ledger_preflight_verb.py src/aeat/entrypoints/cli/test_live_notifications_verbs.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_overview_agenda_verb.py src/aeat/entrypoints/cli/test_overview_backlog_verb.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_overview_explain_verb.py src/aeat/entrypoints/cli/test_profile_censo_verbs.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. Remaining work includes explicit approved-route classification, `test_modelo_export_verb.py`, profile lifecycle fixture cleanup, and guard/closeout rows S94-S95.
