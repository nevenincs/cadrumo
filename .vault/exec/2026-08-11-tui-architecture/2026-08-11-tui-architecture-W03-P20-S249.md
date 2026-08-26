---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a41f295287e0b42c6e8094df1fa265ac72d0271fe4bd563d6d328d4172689e15'
step_id: 'S249'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Privatize the validate_references implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/validate_references.py`

## Changes

- `R` `src/cadrumo/domain/calculations/registry/validate_references.py -> _validate_references.py`
- `M` every registry-internal consumer, repointed
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest <blast radius> -n0` -> `pass` (12 passed on the boundary and cross-domain gates)

## Notes

Every consumer was registry-internal, so privatizing eliminated nothing a
caller outside the package depended on.

Two forms resisted the mechanical sweep and are worth knowing. An import
embedded in a `python -c` subprocess string must stay ABSOLUTE: a relative
import there has no parent package and fails at runtime, which no static check
reports. And the package's own absolute imports must become RELATIVE, because
rewriting `registry.x` to `registry._x` otherwise leaves an absolute PRIVATE
import that the public-API boundary gate forbids.
