---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S53'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P11.S53 modelo compare addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Classify `modelo compare` as an adjacent year/modelo comparison command.
- Audit its revision choice as command-specific comparison selection rather than operator raw-ID chaining.
- Preserve current year/modelo options for the comparison surface.

## Outcome

`modelo compare` remains a year/modelo command and does not require work-unit natural selector options.

## Notes

- No code change was required for this classification decision.
