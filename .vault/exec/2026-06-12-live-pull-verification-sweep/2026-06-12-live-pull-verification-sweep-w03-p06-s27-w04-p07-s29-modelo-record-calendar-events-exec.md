---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S27'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-w03-p06-s27-calendar-local-aeat-axis-exec]]'
  - '[[2026-06-12-live-pull-verification-sweep-w03-p06-s27-w04-p07-s29-calendar-justificante-warning-exec]]'
---

# W03.P06.S27 / W04.P07.S29 Modelo record calendar events

## Scope

Projected persisted Modelo filing records into the overview calendar event
stream while keeping the local filing axis, AEAT submission axis, and
justificante verification axis separate. This makes an application-side filing
record visible as an actual calendar event without treating it as a real-world
AEAT submission unless AEAT evidence and matching justificante metadata prove
that state.

## Description

- Add pure `calendar_events_from_modelo_records()` projection under the
  overview application surface.
- Reuse the existing Modelo-record filing evidence reconciliation so the event
  carries `not_observed`, `accepted`, or `justificante_verified` consistently
  with calendar entries.
- Wire `overview calendar` and `overview calendar --all-profiles` to merge
  persisted Modelo filing-record events with local live snapshot events before
  building the calendar.
- Render calendar events through one shared text helper so filing events show
  modelo, filing year, typed period, local record status, AEAT state, and
  justificante verification consistently.
- Fail closed when local live-event, Modelo-record, or filing-evidence stores
  cannot be read, instead of returning empty evidence that could hide
  unverified AEAT filing state.
- Fail closed in `--all-profiles` as well: evidence-loader refusals are
  re-raised instead of being converted into `profile_skipped`.
- Add unit coverage for local-only filing events and verified AEAT
  justificante filing events.
- Add CLI coverage proving a persisted Modelo 303 filing record appears as an
  `event filing` row with `aeat=justificante_verified` and
  `justificante=true` only after matching persisted justificante metadata is
  present.
- Add CLI coverage proving a corrupt persisted filed-declaration observation
  store refuses calendar rendering rather than silently erasing evidence.
- Add CLI coverage proving `--all-profiles` refuses the same corrupt evidence
  state and does not skip the affected profile.

## Outcome

Changed code:

- `src/aeat/application/overview/_calendar.py`
- `src/aeat/application/overview/__init__.py`
- `src/aeat/entrypoints/cli/_overview.py`
- `src/aeat/application/overview/tests/test_calendar.py`
- `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`

Verification:

- `vaultspec-rag search "cross period clean state justificante AEAT filing evidence calendar modelo verified receipt" --type code --port 8766 --max-results 12 --timeout 180`
  - result: `http_search_timeout`; exact local symbol discovery continued with
    `rg`.
- `.venv\Scripts\python.exe -m ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/__init__.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py::test_modelo_record_projects_local_filing_calendar_event src/aeat/application/overview/tests/test_calendar.py::test_modelo_record_calendar_event_reports_verified_aeat_justificante_axis -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_text_output_names_verified_aeat_evidence -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_refuses_when_local_filing_evidence_store_is_unreadable -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_refuses_when_local_filing_evidence_store_is_unreadable src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_all_profiles_refuses_when_local_filing_evidence_store_is_unreadable -q -rs --tb=short`
  - result: 2 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/overview/tests/test_calendar.py -q -rs --tb=short`
  - result: 77 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q -rs --tb=short`
  - result: 17 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_bulk_pull_text_reports_failures_without_pull_all -q -rs --tb=short`
  - result: 4 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q -rs --tb=short`
  - result: 31 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/modelo/tests/test_import_flow.py::test_import_refuses_justificante_evidence_without_expected_tax_id src/aeat/application/modelo/tests/test_import_flow.py::test_import_refuses_justificante_evidence_for_different_period src/aeat/application/modelo/tests/test_import_flow.py::test_import_refuses_justificante_evidence_for_different_taxpayer src/aeat/application/modelo/tests/test_import_flow.py::test_import_justificante_taxpayer_match_is_case_insensitive -q -rs --tb=short`
  - result: 4 passed.
- `.venv\Scripts\python.exe -m pytest -m unit src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_enrolls_matching_justificante_metadata src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_refuses_wrong_taxpayer_justificante_metadata src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_stamps_matching_current_filing_record src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_does_not_stamp_current_filing_for_wrong_profile_taxpayer -q -rs --tb=short`
  - result: 4 passed.

## Notes

This is local calendar/modelo projection hardening. It does not close the
authenticated live evidence rows: positive AEAT censo, filed-history, and
justificante pulls still require operator-authenticated `pull` runs before
`W02.P04.S10`, `W02.P04.S11`, `W02.P04.S14`, `W03.P05.S18`,
`W03.P05.S22`, or `W03.P06.S27` can be checked complete.
