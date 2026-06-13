---
tags:
  - '#exec'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S06'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `W03.P03.S06` Focused verification

## Description

- Run ruff across touched implementation, test, and registry files.
- Run focused live application, registry, CLI, and overview agenda tests.

## Outcome

Ruff passed. Focused pytest passed with 61 tests.

## Notes

`test_json_schema_conformance.py` was also run and failed broadly with 116 missing registered-schema diagnostics across existing command families.
