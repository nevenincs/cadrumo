---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a70c0a984a4192a203ab285387130aadfa20a9688122997e4456e00dbbb4e963'
step_id: 'S249'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

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
