---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W03.P06.S27 / W04.P07.S29 calendar justificante presented-at review fix

## Scope

Resolve code-review finding LPS-046 for calendar filing evidence timestamp
merging.

## Description

- Source verified calculation-observation `aeat_submitted_at` from the matched
  persisted `Justificante.presented_at` metadata instead of the local
  observation envelope capture time.
- Preserve an existing verified justificante presentation timestamp when a
  same-obligation equal-ranked verified candidate is merged later.
- Add a regression proving a verified Modelo record and a same-period verified
  calculation observation keep the official receipt presentation time.
- Recheck the CLI acquisition verb guard so live filed and expedientes bulk
  acquisition remain under `pull`, with `pull-all` absent.

## Outcome

The calendar can no longer replace an official AEAT receipt presentation time
with a later local capture/import timestamp during same-obligation evidence
merges.

Verification:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_official_calculation_observation_source_with_matching_justificante_is_verified src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_verified_modelo_record_receipt_time_survives_calculation_observation_merge -q --tb=short`
  passed with 2 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short`
  passed with 52 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
  passed with 3 tests.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  passed with 172 tests.

## Notes

This was local backend/calendar hardening only. It does not claim a successful
live AEAT read. The live Modelo 036/censo, filed-history, justificante,
notifications, expedientes, and live-backed calendar proof still require an
operator-completed authenticated session.
