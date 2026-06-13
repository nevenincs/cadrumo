---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S10'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P03.S10`

Added focused overview calendar event tests.

- Modified: `src/aeat/application/overview/test_calendar.py`
- Modified: `src/aeat/entrypoints/cli/test_overview_calendar_verb.py`
- Created: this execution record

## Description

Covered filing event projection from persisted expedientes snapshots, message event projection from persisted notifications snapshots, and CLI JSON output that includes events from real local persisted snapshots.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py -q`
- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py -q -k "calendar or capture_all or live_filed_capture_sources or filed_bulk"`
