---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:40a231566dabdc162d5e55ccdeb706ebfb4c4d3fe935d59f90bdebdf63eb25bb'
step_id: 'S281'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the temporal-selection source scanner, path-keyed sanctioned-site metastate, and Python-source string tests; retain and run the direct temporal behavior suite, update cadence, and remeasure exact reachability.

## Scope

- `temporal registry tests and signal-burndown cadence`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for the sanctioned-site list, AST scanner helpers, and embedded `select_revision` source strings -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` direct temporal behavior suite -> `19 passed`
- `verify:` exact reachability -> `260 unused symbols, 31 unreachable modules, 0 orphaned tests`
