---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a021b4306c57227b326821fdec07edb9495f46653c8357fc1d4582317becd1f3'
step_id: 'S316'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the acceptance-wall node-id catalogue, nested CI runner, and source-mutating proof

## Scope

- `acceptance wall test metadata`
- `stale cross-reference`
- `focused CI workflow gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_acceptance_wall_catalogue.py`
- `D` `src/cadrumo/tests/acceptance_wall_catalogue.py`
- `M` `src/cadrumo/tests/test_host_load_hook.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q -n0 -o addopts='' dev/ci/tests/test_ci_workflow.py -k integration` -> `fail`

## Notes

The owning `ci-full.yml` integration lanes remain wired and 38 focused CI workflow checks pass. Two peer-owned assertions in `dev/ci/tests/test_ci_workflow.py` still expect older marker expressions that omit the live `windows_only` and `tui_render` exclusions; this Step does not weaken those recipes to satisfy stale string checks.
