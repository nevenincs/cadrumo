---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4b4b85a974feaa5312d34a7b5fbe45ea6d469e60d45a8ecf7040786699112a7c'
step_id: 'S316'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
