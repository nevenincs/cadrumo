---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S75'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P07.S75` Application selector and lifecycle verification

Step scope: `src/aeat/application/modelo`.

## Description

- Run selector tests for visible-target work-unit resolution and calculation revision selectors.
- Run filing lifecycle tests for current pointer, filing, and duplicate revision behavior.
- Run export tests for filed and verified revision selection behavior.
- Run adjacent application tests for history, reconciliation, and taxation comparison.

## Outcome

Focused application modelo verification passed:

- `src/aeat/application/modelo/test_selectors.py`: 13 passed.
- `src/aeat/application/modelo/test_history.py`, `test_reconcile.py`, and `test_taxation_comparison.py`: 20 passed.
- `src/aeat/application/modelo/test_file_flow.py`: 30 passed.
- `src/aeat/application/modelo/test_export.py`: 15 passed.

## Notes

The first combined command timed out after 184 seconds, and parallel reruns timed out for `test_file_flow.py` and `test_export.py` because those files are slow in this workspace. Serial reruns with a longer timeout passed.
