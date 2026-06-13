---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S24'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P07.S24 split modelo work command family behind existing Typer wiring

Scope: `W03.P07` modelo CLI command extraction.

## Description

- Add a dedicated `_modelo_work` module that owns construction of the `modelo work` Typer group.
- Replace the inline `work_app` construction in `_modelo` with `create_work_app`.
- Preserve the existing registration point through `app.add_typer(work_app, name="work")`.

## Outcome

The command group factory is now isolated from the monolithic `_modelo` module while preserving the public command tree.

## Notes

This is a conservative extraction. The individual `work` command bodies remain in `_modelo` until the next decomposition slice can move command families without changing command discovery or schema registration.
