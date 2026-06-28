---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S07'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P01.S07`

Added the filed capture-all output payload schema.

- Modified: `src/aeat/entrypoints/cli/_app_live_payloads.py`
- Created: this execution record

## Description

Registered the `app.live.filed.capture_all` output schema and failure-row payload so bulk capture results can report counts, persisted paths, artefact references, calculation observation keys, and explicit failures.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/entrypoints/cli/test_registry_cli.py -q -k "capture_all or live_filed_capture_sources"`
- `./.venv/Scripts/python.exe -m ruff check src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/test_registry_cli.py`
