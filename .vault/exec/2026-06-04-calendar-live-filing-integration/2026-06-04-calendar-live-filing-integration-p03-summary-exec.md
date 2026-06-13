---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
---

# `calendar-live-filing-integration` phase summary

Completed the planned local calendar event integration and bulk filed-declaration capture surface.

## Summary

The overview calendar now remains obligation-derived while also carrying observed AEAT events from persisted local live-read snapshots. Filing events are projected from expedientes declarations; message events are projected from notifications. The live filed backend now has a read-only bulk capture service and `app live filed capture-all` CLI command for all registry modelos or a repeated `--modelo` subset.

## Verification

- `./.venv/Scripts/python.exe -m ruff check src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/live/__init__.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/_app_live.py src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `./.venv/Scripts/python.exe -m pytest src/aeat/application/overview/test_calendar.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/entrypoints/cli/test_overview_calendar_verb.py src/aeat/entrypoints/cli/test_registry_cli.py -q -k "calendar or capture_all or live_filed_capture_sources or filed_bulk"`
- `./.venv/Scripts/aeat.exe app live filed capture-all --help`
- `./.venv/Scripts/vaultspec-core.exe vault plan check .vault/plan/2026-06-04-calendar-live-filing-integration-plan.md`

## Caveat

No remote AEAT live capture was run in this execution. The code path is live-read gated and requires an authenticated operator session; coverage for "all modelos" is registry-driven, while actual remote availability still depends on AEAT's declaration-register behavior per modelo and year.
