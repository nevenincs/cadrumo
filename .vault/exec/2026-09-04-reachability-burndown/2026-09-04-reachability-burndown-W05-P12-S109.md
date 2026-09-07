---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f56b6cec00117fdab9bebe9f82829785eec691cb63d31951a37d0ecfa8efc069'
step_id: 'S109'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the eleven declared Modelo devtools fixtures into SURFACES, gate the unregistered-registry class, and classify the remaining orphaned-test clusters

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_every_fixture_registry_is_registered.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests src/cadrumo/entrypoints/tui/devtools/tests -n0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/devtools/surfaces.py` -> `pass`

## Notes

The devtools classification was written on a false premise and corrected before
the step closed. The first evidence claimed `modelo_fixtures` was design-time
authority read by `dev/tui/_coverage.py` and `dev/tui/_harness.py`; the ledger
citation gate refused it, and it was right -- those files name sibling devtools
modules and never this one. Its only reader was its own test. The module was
wired into `SURFACES` instead of classified, so both the module row and its
orphaned-test row were removed rather than kept.

The reach this achieved is `module-exec-only`, not full runtime reachability:
the devtools package is entered through `python -m`, which the audit roots
separately from the console scripts. Eight devtools modules moved from
`unreachable` to `module-exec-only` on this change, `modelo_fixtures` among
them. An earlier note in this record said `surfaces.py` was reachable; that
was imprecise and is corrected here.

Three `test_module` rows spent by the preceding step's facade retirement were
removed here rather than in that step, where they belonged.
