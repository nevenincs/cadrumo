---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S21'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P04.S21 natural-key work verify

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Confirm `modelo work verify` accepts a natural filing target and revision selector options.
- Preserve the command-specific default of selecting the current draft revision for verification.
- Cover verification of a real current draft under a natural target.

## Outcome

Verification no longer requires operators to copy a calculation revision id when the current draft is the intended target.

## Notes

- Focused CLI lifecycle tests passed.
