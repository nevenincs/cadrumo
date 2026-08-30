---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2f64b53ddda028d879f4d20af17c3ecab720aa721948808539fbbec48fe8def1'
step_id: 'S27'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Atomically replace the C1 review selection outcome with modelo.workspace.overview, register the closed destination and route-factory census, and prove zero remaining modelo.work.review routes or aliases

## Scope

- `src/cadrumo/entrypoints/tui/modelo/routes.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/routes.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/app.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_select_cli.py`
- `M` `dev/tests/test_import_hygiene_gate.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)

## Notes

The route census test is left DELIBERATELY RED. No non-circular authority exists
to derive its expected destination set from: any source available to the test is
either the census under test or derived from it, so an expected set would assert
the code against itself. Recorded as an open question rather than resolved by a
hardcoded set, which would be the enumerated-subject-list antipattern this
campaign has ruled against.

The seam entry retargeting in the hygiene gate was verified by diffing the
constant against HEAD rather than by grep: the changed key renames
`_run_review_destination_for_selected_unit` to
`_run_workspace_destination_for_selected_unit`, which a pattern keyed on the
constant name or on `modelo` does not match.
