---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P02.S03`

Added overview event models and pure projection helpers.

- Modified: `src/aeat/application/overview/__init__.py`
- Created: this execution record

## Description

Added `OverviewCalendarEventType`, `OverviewCalendarEvent`, snapshot projection helpers, deterministic event sorting, and event de-duplication. Filing events come from persisted expedientes declarations; message events come from persisted AEAT notification snapshots.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py -q`
- `./.venv/Scripts/python.exe -m ruff check src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py`
