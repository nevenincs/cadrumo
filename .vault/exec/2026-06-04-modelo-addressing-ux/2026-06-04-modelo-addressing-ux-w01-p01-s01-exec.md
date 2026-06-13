---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S01'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S01 selector request result ambiguity and error objects

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Add typed selector request, resolution, candidate, and state models.
- Add typed selector refusals for no active bucket, missing exact work unit, contradictory selector flags, visible-target ambiguity, and registry revision conflict.
- Register selector refusal errors in the application error-code registry so collection enforces the public error contract.

## Outcome

The application selector boundary now has explicit typed request/result models and ambiguity/refusal objects for later CLI rendering.

## Notes

- Focused selector tests and ruff passed for this slice.
