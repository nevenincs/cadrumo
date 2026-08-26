---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2a558b53a9803c60117f5a2b71779785c72cb1f1606b0d5115bd548cc56e472b'
step_id: 'S217'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Privatize the m303_orden_raw_models implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/m303_orden_raw_models.py`

## Changes

- `R` `src/cadrumo/domain/calculations/registry/m303_orden_raw_models.py -> _m303_orden_raw_models.py`
- `M` every live consumer, repointed
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ -n0` (blast radius) -> `pass`

## Notes

The module had no external consumer but generated docs stubs, so privatizing
it eliminated nothing a caller depended on. Every live reference was repointed
and the API stubs regenerated.

Two sweep lessons are recorded because each cost a real failure. A rename must
sweep every file type that can carry a PATH, not only those carrying imports -
a .toml naming three of these by their old public paths broke the embed
classification gate. And a mechanical rewrite can CREATE a violation rather
than leave a stale one: rewriting `registry.x` to `registry._x` turned a legal
absolute import into an absolute PRIVATE import, which the public-API boundary
gate forbids; that consumer now imports relatively.
