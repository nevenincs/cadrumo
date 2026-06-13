---
tags: ["#exec", "#calendar-live-filing-integration"]
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` `P01.S05`

Added the `aeat app live filed capture-all` CLI command.

- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, `src/aeat/locales/ca.yml`, `src/aeat/locales/hu.yml`
- Created: this execution record

## Description

Exposed bulk read-only filed-declaration capture through the live filed CLI group with `--from-year`, `--to-year`, `--output-root`, and repeatable `--modelo` options. Help text states the no-submit/read-only contract.

## Tests

- `./.venv/Scripts/python.exe -m pytest src/aeat/entrypoints/cli/test_registry_cli.py -q -k "capture_all or live_filed_capture_sources"`
- `./.venv/Scripts/aeat.exe app live filed capture-all --help`
