---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P01.S04`

Added bulk filed-declaration capture reporting and service support.

- Modified: `src/aeat/application/live/__init__.py`
- Created: this execution record

## Description

Added `BulkFiledDataCaptureReport`, `FiledDataCaptureFailureRow`, `filed_data_capture_failure_row`, and `capture_filed_data_bulk`. The service shares one authenticated live-read session, iterates requested modelos and years, persists successful observations and artefacts, and records per-modelo/per-declaration failures explicitly.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/application/live/test_filed_bulk_capture.py -q`
- `./.venv/Scripts/python.exe -m ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_filed_bulk_capture.py`
