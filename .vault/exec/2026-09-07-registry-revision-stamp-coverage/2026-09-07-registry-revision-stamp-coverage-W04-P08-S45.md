---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:71bb1d0b3fb05ef703a2484b797dce635250a5466a7deb6ad5ceacabc08d095e'
step_id: 'S45'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Collect integration suites explicitly and run the applicable integration selection without relying on default addopts

## Scope

- `src/cadrumo`

## Changes

- `verify:` `uv run pytest --co -q -m integration src/cadrumo/entrypoints/cli/tests/test_prorrata_register_seed_cli.py src/cadrumo/entrypoints/cli/tests/test_modelo_local_observation_cli.py src/cadrumo/entrypoints/cli/tests/test_overview_calendar_local_evidence.py src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_prorrata_register_seed_cli.py src/cadrumo/entrypoints/cli/tests/test_modelo_local_observation_cli.py src/cadrumo/entrypoints/cli/tests/test_overview_calendar_local_evidence.py src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py` -> `pass`

## Notes

Repository-wide integration collection reached 5,624 selected tests before 16
unrelated collection errors from deleted `entrypoints/tui/devtools` modules in
the shared worktree. The campaign's applicable 70-test integration selection
collected explicitly and passed in full.
