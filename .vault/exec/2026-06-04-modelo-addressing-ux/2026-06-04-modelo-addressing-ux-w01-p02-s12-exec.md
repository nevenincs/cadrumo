---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S12'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S12 duplicate calculation pointer coverage

Scope:
- `src/aeat/application/modelo/test_file_flow.py`

## Description

- Add a real calculate-flow regression test for duplicate draft reuse.
- Clear the current pointer through the real work-unit repository, rerun an identical calculation, and assert the persisted current pointer is restored to the draft revision.
- Assert filed pointers remain unset during duplicate draft reuse.

## Outcome

The duplicate calculation current-pointer behavior is proven through the production calculation and persistence path.

## Notes

- Focused file-flow tests passed.
