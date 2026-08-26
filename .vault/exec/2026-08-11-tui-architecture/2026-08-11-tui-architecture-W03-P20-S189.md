---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:dbacab86429325776d4235442edbed3e0f9638f2d316bbf7a158575e16ecf59e'
step_id: 'S189'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Privatize the cross_revision_divergence implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/cross_revision_divergence.py`

## Changes

- `R` `src/cadrumo/domain/calculations/registry/cross_revision_divergence.py -> _cross_revision_divergence.py`
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
