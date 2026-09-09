---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:99eec1015eb5716ed232300e5df0671f7d29d949bee5fd082324b8000424da1c'
step_id: 'S335'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the synthetic runtime-floor detector framework with one live configuration agreement check

## Scope

- `runtime-floor packaging tests`
- `live toolchain declarations`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/packaging/tests/test_runtime_floor_singularity.py`
- `A` `dev/packaging/tests/test_runtime_floor.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_runtime_floor.py dev/packaging/tests/test_container_base_image.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
