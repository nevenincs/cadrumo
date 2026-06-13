---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S10'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P03.S10 - legacy lifecycle bodies replaced

Scope: replace legacy lifecycle command bodies with registrar mounting only.

## Description

- Wire `register_work_lifecycle_commands` into `_modelo.py`.
- Remove the old decorated `work_create`, `work_list`, `work_status`, `work_rename`, and `work_discard` functions from the legacy root.
- Remove root-only lifecycle helper definitions and imports that became unused.
- Tighten the `_modelo.py` frozen size budget from 4248 to 3735 lines after extraction.

## Outcome

`_modelo.py` now mounts lifecycle commands through the focused registrar and has shrunk from 4248 lines to 3735 lines. The size guard freezes that new baseline.

## Notes

Verification: `test_cli_module_size.py` passed after lowering the budget.
