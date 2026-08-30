---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:d920485956d6388674f855a530961a5641d6758626433231a5917e9a877a242d'
step_id: 'S58'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove C2 route replacement, destination and factory census, projection-kind coverage, large and deep schemas, empty and paged rows, overflow, provenance, refusals, capabilities, keyboard focus, all locales, geometries, and themes before availability

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c2_workspace_accessibility.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c2_workspace_accessibility.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)

## Notes

The matrix proves rendering, localization, geometry and theme behaviour WHEN
MOUNTED. It does not prove availability; the production host does. Reachability
holds only because that host landed under `W05.P11.S27`, and this record must not
be read as the matrix establishing it.
