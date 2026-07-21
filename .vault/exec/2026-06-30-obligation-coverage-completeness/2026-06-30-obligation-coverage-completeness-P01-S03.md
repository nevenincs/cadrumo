---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Attach the coverage report to the calendar, agenda, and backlog read models.

## Scope

- `src/aeat/application/overview/_calendar.py`

## Description

- Add an always-populated `coverage` field to the `OverviewCalendar` read model,
  computed at the calendar build from the surfaced entry set.
- Inherit `coverage` into `OverviewAgenda` and `OverviewBacklog`, which compose the
  calendar, so every default surface carries the same reconciliation.
- Re-export the coverage types from the overview package.

## Outcome

The coverage report is populated regardless of the `--show-suppressed` flag, so the
default surface always exposes what it could not positively scope. All 220
application-overview tests pass.

## Notes
