---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f36ea3df5b6e0d3e4231e5e44934e5842320a88007d50c6ba6bdd9770dfaed98'
step_id: 'S154'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Restrict calculation-route ownership checks to scalar bindings, deriving row-producing bindings from their aggregation operation so existing detail-row and export channels are not misclassified as missing source-mesh resolvers.

## Scope

- `calculation novel-source guard and live route-ownership tests`

## Changes

- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py -k "novel_source_binding or row_producing_binding"` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/modelo/calculation_actions.py src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py` -> `pass`

## Notes

The full live gate now reports only `gasto193_contributor`; the three row-only source families were correctly removed from the scalar population. The remaining source has two scalar `sum` bindings and no secure resolver, so it remains red for the registry/input mechanism rather than being deferred.
