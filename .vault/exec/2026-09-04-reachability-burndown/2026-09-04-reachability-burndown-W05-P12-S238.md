---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9fb157494673e132a2511070b57c50ff8b6f40d535ee87777c5e83ced67e2ccb'
step_id: 'S238'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
