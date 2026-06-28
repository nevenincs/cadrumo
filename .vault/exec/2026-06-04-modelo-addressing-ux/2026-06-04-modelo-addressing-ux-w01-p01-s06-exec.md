---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S06'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S06 selector package exports

Scope:
- `src/aeat/application/modelo/__init__.py`

## Description

- Export selector request, result, candidate, state, errors, and resolver functions from the modelo application package.
- Keep the selector boundary available to CLI and adjacent application consumers through the existing top-level application package surface.

## Outcome

Callers can import the selector boundary from `aeat.application.modelo` without reaching into private implementation modules.

## Notes

- Ruff passed after adding the exports.
