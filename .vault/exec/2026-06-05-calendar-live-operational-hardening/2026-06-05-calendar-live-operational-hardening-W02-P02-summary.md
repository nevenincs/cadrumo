---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `calendar-live-operational-hardening` `W02.P02` summary

Operator live facades were expanded for message and expedientes workflows.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/entrypoints/cli/_app_live_payloads.py`
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`

## Description

Added notifications latest and expedientes capture-all. Bulk expedientes capture persists one aggregate snapshot for coherent latest/readback behavior.
