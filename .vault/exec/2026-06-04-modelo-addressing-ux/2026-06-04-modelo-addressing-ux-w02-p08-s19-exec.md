---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S19'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P08.S19 visible-target work create reuse

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Change `modelo work create` to resolve an existing visible filing target before defaulting a registry revision.
- Keep explicit `--revision` conflict refusal through the application selector.
- Update reuse messages to describe idempotency on modelo/year/period.

## Outcome

Creating a work unit for an already-active visible filing target now resumes that unit even when the second invocation omits `--revision`.

## Notes

- Focused CLI coverage verifies no-revision create returns `modelo.work.reuse` with the original work-unit id.
