---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S16'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S16 - calendar justificante state consistency

## Description

- Enforce that calendar filing evidence cannot report `aeat_submission_state = justificante_verified` unless `justificante_verified = true`.
- Enforce that calendar filing events cannot report `justificante_verified = true` unless their AEAT submission state is also `justificante_verified`.
- Add focused model-boundary tests so contradictory live/persisted evidence fails before rendering a misleading calendar row.

## Outcome

`OverviewCalendarFilingEvidence` and `OverviewCalendarEvent` now reject contradictory justificante state. This strengthens the calendar/modelo filing distinction the feature requires: local ready-to-file records, AEAT observed submissions, AEAT accepted records, and justificante-verified filings remain separate states, and the verified state cannot be represented without the explicit boolean proof marker.

## Verification

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q` passed with 54 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "integration or not integration" -q` passed with 442 tests.

## Notes

This step does not close the remaining live Modelo 036/G313 proof. The final censo-derived obligation reconciliation still requires a live authenticated taxpayer profile whose Cl@ve identity matches the active profile tax identity.
