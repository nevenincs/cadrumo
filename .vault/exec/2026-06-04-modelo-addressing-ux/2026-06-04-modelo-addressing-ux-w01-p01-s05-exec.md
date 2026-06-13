---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S05 registry revision conflict refusal

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Detect a requested `revision_id` that conflicts with the single active work unit already present for the visible filing target.
- Refuse the conflict before any exact-target creation path can run.
- Return candidate metadata on the existing active work unit for operator guidance.

## Outcome

The selector prevents silently creating a second active work unit for the same visible filing target when the requested registry revision differs from the active workspace.

## Notes

- Tests cover requested revision conflict and candidate metadata.
