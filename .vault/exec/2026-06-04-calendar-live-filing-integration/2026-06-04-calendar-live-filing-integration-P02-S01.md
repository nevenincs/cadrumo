---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S01'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P02.S01`

Extended the overview calendar CLI payload schema to include observed local event rows.

- Modified: `src/aeat/entrypoints/cli/_overview_payloads.py`
- Created: this execution record

## Description

Added `OverviewCalendarEventPayload` and exposed `events` on `OverviewCalendarResult` so JSON output can carry AEAT filing and notification events alongside legal obligation entries.

## Tests

- `./.venv/Scripts/python.exe -m ruff check src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/_app_live.py src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py -q -k "calendar or capture_all or live_filed_capture_sources or filed_bulk"`
