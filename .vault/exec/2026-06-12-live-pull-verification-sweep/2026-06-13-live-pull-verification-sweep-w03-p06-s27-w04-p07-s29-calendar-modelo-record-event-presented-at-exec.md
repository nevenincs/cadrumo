---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S27'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W03.P06.S27 / W04.P07.S29 calendar Modelo-record event presented-at

## Scope

Harden the overview calendar so verified Modelo-record filing events are dated
from official AEAT justificante presentation time instead of the local app
filed/import timestamp.

## Description

- Added `aeat_submitted_at` to `OverviewCalendarEvent` and to the overview CLI
  event payload schema.
- Changed `calendar_events_from_modelo_records` so local ready-to-file records
  keep `record.filed_at.date()`, while justificante-verified AEAT records use
  the matched `Justificante.presented_at.date()`.
- Rendered `aeat_submitted_at` in calendar event text output when present.
- Added focused assertions proving local app filing events remain local-dated
  and verified AEAT Modelo-record events use the official submission date and
  timestamp.

## Outcome

The calendar now distinguishes the app's local ready-to-file filing record
from the real-world AEAT filing time at the event level. A Modelo filing record
with verified justificante metadata appears as an AEAT-submitted filing on the
official `presented_at` date, while unsubmitted/local-only records still appear
on the local filed date with `aeat=not_observed`.

Verification:

- `uv run ruff check src/aeat/application/overview/_calendar_models.py
  src/aeat/application/overview/_calendar.py
  src/aeat/entrypoints/cli/_overview_payloads.py
  src/aeat/entrypoints/cli/_overview.py
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py
  src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_projects_local_filing_calendar_event
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_calendar_event_reports_verified_aeat_justificante_axis
  -q --tb=short` passed with 2 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_text_output_names_verified_aeat_evidence -q --tb=short`
  passed with 1 test.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py
  src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short`
  passed with 116 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short`
  passed with 94 tests.

## Notes

This is local calendar/modelo evidence hardening. It does not claim successful
live AEAT authentication or a live AEAT read; the Cl@ve completion blocker
remains open for live-backed censo, filed-history, justificante, notification,
expediente, and submitted-calendar proof.
