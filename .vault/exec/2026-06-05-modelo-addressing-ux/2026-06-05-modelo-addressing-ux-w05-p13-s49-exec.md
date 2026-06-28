---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S49'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P13.S49 Centralized Addressing Static Guard

Scope: prevent CLI-local raw-id regexes and duplicated work/revision selector policy from returning.

## Description

- Extend `test_architecture_boundaries.py` with a guard forbidding CLI modules from importing or calling low-level work-address and calculation-revision-address resolver primitives.
- Keep raw exact-id shape validation confined to `_modelo_cli_support.py`.
- Preserve top-level application facade consumption as the allowed route for modelo work and revision addressing.

## Outcome

The architecture boundary test suite now fails if modelo CLI modules bypass the centralized operator-addressing facades or reintroduce direct low-level selector calls.

## Notes

Rendering and payload modules may still display current revision identifiers; the guard targets resolver policy, not output projection.
