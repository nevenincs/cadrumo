---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S09'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P03.S09 - work lifecycle command registrar

Scope: extract work create, list, status, rename, and discard registration into a focused module.

## Description

- Add `src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py`.
- Move lifecycle Typer command registration for `create`, `list`, `status`, `rename`, and `discard` into that module.
- Inject root-owned shared CLI callbacks into the registrar rather than importing the legacy root.
- Keep command names and public argument shapes unchanged.

## Outcome

The lifecycle commands now register from `_modelo_work_lifecycle_cli.py`. The new module consumes application facades and shared rendering helpers, while `_modelo.py` no longer contains the decorated lifecycle command bodies.

## Notes

Verification: Ruff passed on touched files. Focused static and lifecycle CLI tests passed.
