---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S14'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P03.S14 work-unit CLI pointer payloads

Scope:
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Add current calculation, filed calculation, and current filing pointer fields to shared work-unit CLI payloads.
- Populate full and short calculation revision pointer ids from real work-unit state.

## Outcome

Work-unit JSON payloads now expose the current and filed pointers operators need for discovery while preserving existing fields.

## Notes

- Focused ruff and CLI tests passed for this slice.
