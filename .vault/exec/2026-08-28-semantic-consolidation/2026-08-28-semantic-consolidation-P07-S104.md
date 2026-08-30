---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:40e5b0cb0ba847951d4a59ce52dad62d9d081c30ebbfeb45c07b94a69fd92841'
step_id: 'S104'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the module-level re-export facade in calculation_revision, where thirteen names were imported solely to be listed in its __all__ and reached that way by thirty-two consumers

## Scope

- `src/cadrumo/domain/modelos/calculation_revision.py`

## Changes

- (no code change: the split was backed out)

## Notes

The hierarchy split was applied and then reverted by the concurrent git session,
which restored tracked files underneath it. Between those two points a commit
landed on the half-applied state, leaving a HEAD that imported
`core.errors.hierarchy` without tracking the module -- a clean checkout could
not import `domain/fincas/errors.py`. The git owner reverted it and HEAD is
consistent again.

Four untracked modules from the attempt remain on disk and are unreferenced by
HEAD, but the tree-walking gates import every module under `src/`, so
`hierarchy.py`'s registered exception subclasses fail to bind and four tests in
`test_exception_base_hygiene` and `test_registry_enforcement` fail. They need
removing; that was left to the operator.
