---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S147'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S147 Overview Calendar Test Split

## Scope

Split the current overview calendar taxpayer-model and entity-type regression group into a focused test module.

## Description

- Moved taxpayer-model, entity-type, no-window, agenda/backlog, and locale regression tests into `test_calendar_taxpayer_model.py`.
- Left shared calendar helpers and core calendar tests in `test_calendar.py`.
- Preserved real behavior assertions without mocks, skips, xfails, or duplicated business logic.

## Outcome

`test_calendar.py` is now below the current size budget, and the new focused test module is below the default module threshold.

## Notes

The split is mechanical; assertions were preserved.
