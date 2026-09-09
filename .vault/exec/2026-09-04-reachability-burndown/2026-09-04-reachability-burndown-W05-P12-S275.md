---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c20cbdeafe2d1ed9b1aff185207a6e40eeead0160249c6ce4edd0afd867beba9'
step_id: 'S275'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only Modelo edit version-header DTO and parser because no runtime dispatcher consumes them; retain live versioned edit models and integration behavior, update cadence, and remeasure exact reachability.

## Scope

- `Modelo edit models and focused integration tests`

## Changes

- `M` `src/cadrumo/application/modelo/edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` focused Ruff check -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/modelo/tests/test_edit_models.py` -> `14 passed`
- `verify:` exact reachability -> `266 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The removed DTO/parser had no product dispatcher caller and existed solely for a test that passed an arbitrary mapping to the helper. The actual versioned edit request/result models and their integration suite remain. Exact unused symbols improved from 267 to 266; modules and orphan tests are unchanged.
