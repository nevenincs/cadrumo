---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
step_id: 'S17'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S17 - active AEAT register status for calendar evidence

## Description

- Require AEAT declaration-register status `ALTA` before an expedientes event can produce per-obligation submitted evidence.
- Require `FiledDeclaracionObservation.status = ALTA` before captured filed-declaration artefacts can mark a calendar obligation submitted or justificante-verified.
- Keep non-`ALTA` register rows visible as calendar events with their raw status, without upgrading the obligation evidence state.
- Add application and CLI-storage regression tests for non-`ALTA` rows with justificante artefacts.

## Outcome

Calendar projection now respects AEAT register current-state semantics at the local aggregation boundary. A cancelled, superseded, or otherwise non-`ALTA` live register row can remain visible for operator history, but it cannot satisfy the calendar's AEAT submitted or justificante-verified evidence state for the obligation.

This closes a backend consistency gap between live acquisition, which already prefers `ALTA` rows, and the local overview projection, which previously trusted any persisted filed-declaration observation.

## Notes

Verification passed:

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 65 tests.

The live Modelo 036/G313 censo-derived obligation proof remains open until a matching taxpayer profile authenticates successfully.
