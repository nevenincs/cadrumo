---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P02.S02`

Wired persisted local live-read snapshots into `aeat app overview calendar`.

- Modified: `src/aeat/entrypoints/cli/_overview.py`
- Created: this execution record

## Description

Loaded local persisted expedientes and notifications snapshots for the active bucket and projected them into calendar events. Text output now reports event counts and event rows; JSON output includes the new `events` field.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/entrypoints/cli/test_overview_calendar_verb.py -q`
- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py -q -k "calendar or capture_all or live_filed_capture_sources or filed_bulk"`
