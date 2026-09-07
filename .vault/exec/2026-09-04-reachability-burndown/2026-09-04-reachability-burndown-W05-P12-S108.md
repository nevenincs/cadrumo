---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:60ccf314e0ae422c1d287f1a6dfcd22e4755bc07f9b4b0e2d6d7e7e56f26d97a'
step_id: 'S108'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Retire the command_graph package-init alias, repoint its seven consumers to command_specs.COMMAND_GRAPH, and fix the owner-check silencing bug in the narrowing detector

## Scope

- `dev/agent_eval/_runner.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/__init__.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_capability_family_isolation.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_resolution_cost_budget.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_side_effect_contract.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_resolution_defers_capabilities.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_state_free_capability_isolation.py`
- `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `M` `dev/agent_eval/_runner.py`
- `M` `dev/quality/narrowing_delegators.py`
- `M` `dev/quality/tests/test_narrowing_delegators.py`
- `M` `dev/quality/unconsumed_export_ratchet.toml`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_narrowing_delegators.py -n0` -> `pass`
- `verify:` `just check-narrowing-delegators` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.import_hygiene_scan` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.facade_export_scan` -> `pass`
- `verify:` `uv run --no-sync python -m pytest src/cadrumo/entrypoints/cli/tests/test_cli_resolution_cost_budget.py src/cadrumo/entrypoints/cli/tests/test_resolution_defers_capabilities.py src/cadrumo/entrypoints/cli/tests/test_state_free_capability_isolation.py src/cadrumo/core/tests/test_external_constants_centralisation_part2.py -m '' -n0` -> `fail`

## Notes

The two failures in `test_resolution_defers_capabilities.py` are pre-existing and
not caused by this change. They were reproduced in a detached baseline worktree
checked out at the commit preceding the repoint, with the `command_graph` alias
still present: the same two cases fail there, 2 failed / 14 passed. The baseline
worktree was created for the comparison and removed afterwards.

`dev/quality/unconsumed_export_ratchet` remains red on one entry,
`application/modelo/edit_services.py`, introduced by a peer commit retiring the
edit facade. It is left unabsorbed rather than recorded, so it stays visible to
its owner. Every entry this campaign spent was lowered or removed in this step.
