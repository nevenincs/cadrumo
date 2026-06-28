---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S77'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S77 Google Calc Sheets Apply Decomposition

Scope: decompose Google calc sheets apply adapter by Sheets API write concern behind the outbound Google facade.

## Description

- Extract value-write payload builders into `src/aeat/adapters/outbound/google/_calc_sheets_apply_values.py`.
- Keep `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` as the orchestration module that owns Drive folder lookup, spreadsheet creation, tab management, clearing, value batch update, and structural batch update.
- Re-import the moved helpers through `src/aeat/adapters/outbound/google/_calc_sheets_apply.py` so same-package adapter tests and existing private compatibility continue to work.
- Leave the top-level Google package facade unchanged.

## Outcome

The calc sheets apply adapter now separates Sheets value-write payload construction from Drive and Sheets orchestration without changing Google export behavior or public package exports.

## Notes

No application, entrypoint, or domain consumer imports the new private value-write module directly.
