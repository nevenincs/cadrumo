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

# W03.P06.S27 / W04.P07.S29 expedientes event submitted-at

## Scope

Preserve official AEAT expediente `presented_at` timestamps through calendar
events, event-derived filing evidence, and event enrichment.

## Description

- Stamped active expedientes filing events with `aeat_submitted_at` from the
  AEAT declaration register row's `presented_at` timestamp.
- Changed observed-event filing evidence projection to preserve
  `event.aeat_submitted_at` instead of downgrading the timestamp to midnight on
  `event_date`.
- Propagated stronger row evidence timestamps back into enriched calendar
  events when matching filing evidence upgrades an event's submission state.
- Added application and CLI assertions proving expedientes-derived events and
  evidence carry the official timestamp.

## Outcome

Observed AEAT filed events from expedientes no longer lose the official filing
time. The calendar row and event surfaces now agree on the real AEAT
submission timestamp when the source is an authenticated AEAT declaration
register snapshot.

Verification:

- `uv run ruff check src/aeat/application/overview/_calendar.py
  src/aeat/application/overview/tests/test_calendar.py
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py
  src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py::test_expedientes_snapshots_project_filing_events_inside_range
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_expedientes_event_marks_observed_submission_but_not_justificante_verified
  -q --tb=short` passed with 2 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_json_includes_local_live_snapshot_events -q --tb=short`
  passed with 1 test.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py
  src/aeat/application/overview/tests/test_calendar_filing_evidence.py
  src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short`
  passed with 116 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short`
  passed with 94 tests.

## Notes

This is local projection hardening over persisted expedientes snapshots. It
does not claim a successful live AEAT read in this session; live-backed censo,
filed-history, justificante, notification, expediente, and submitted-calendar
proof remains blocked on operator-mediated Cl@ve completion.
