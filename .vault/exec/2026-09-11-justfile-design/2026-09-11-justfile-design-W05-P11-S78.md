---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:3ab30818fd6ffc69fc14f59d67ad7c54629f63bf0be67c49c78eda3aa84fb270'
step_id: 'S78'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Make the registry test signal fail closed through collection and exact artifact-backed load preflights before granular lanes, and enroll every registry-owned test population

## Scope

- `Justfile`
- `dev/test_runs`
- `dev/tests/test_lane_reachability.py`

## Changes

- `M` `justfile`
- `M` `dev/test_runs/__main__.py`
- `M` `dev/test_runs/command.py`
- `M` `dev/test_runs/lanes.py`
- `M` `dev/test_runs/tests/test_command.py`
- `M` `dev/test_runs/tests/test_lanes.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/test_runs/tests/test_command.py dev/test_runs/tests/test_lanes.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/tests/test_lane_reachability.py::<four registry ownership checks>` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/test_runs` -> `pass`
- `verify:` `just --show test-registry` -> `pass`
- `verify:` `just test-registry` -> `fail`

## Notes

- The live registry remains unloadable during the concurrent refactor: collection currently raises `PydanticSchemaGenerationError` for `Modelo`, and artifact-backed loading raises it for `TaxDomain`. The improved signal reports those as collection and load preflight failures and blocks all granular lanes.
- No commit was created because another active process holds the shared worktree's Git index lock. No unrelated changes were staged or altered.
