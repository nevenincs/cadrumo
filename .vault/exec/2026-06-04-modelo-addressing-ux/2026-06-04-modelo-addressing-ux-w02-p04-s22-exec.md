---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S22'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P04.S22 natural-key work file

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Confirm `modelo work file` accepts a natural filing target and revision selector options.
- Preserve the command-specific default of selecting the current verified-complete revision for filing.
- Cover natural-key filing through the real selector path up to the real filing-obligation gate.

## Outcome

The filing command resolves the current verified revision under a visible target before applying the calendar workflow gate.

## Notes

- The focused test intentionally reaches the real `NO_PENDING_OBLIGATION` refusal because the current calendar has no open filing window for the selected historical period.
