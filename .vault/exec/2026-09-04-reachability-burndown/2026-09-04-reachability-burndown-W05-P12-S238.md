---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:94382de24829164e5e2f0b51b3f852e0dfa49dee49b9b8bf27a8c2c7cf51f643'
step_id: 'S238'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Pin app.live.portals.list --modelo to the full canonical Modelo enum at the command boundary, replacing its late malformed-token refusal while preserving suppressed-code portal lookup and the shared typed boundary envelope.

## Scope

- `Live portals command spec/handler/tests`
- `accepted closed-value-axis decision`
- `focused closed-axis and portal gates`
- `exact signal`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_live_portals_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_portals_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_live_portals_verbs.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_app_live_portals_command_specs.py src/cadrumo/entrypoints/cli/_app_live_portals_cli.py src/cadrumo/entrypoints/cli/tests/test_live_portals_verbs.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" --basetemp .tmp/pytest-s238 src/cadrumo/entrypoints/cli/tests/test_live_portals_verbs.py src/cadrumo_harness/mcp/tests/test_closed_value_axis_gate.py` -> `fail`
