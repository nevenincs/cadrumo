---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8938745a9c165c59783cab8ac6c5fa396b352272c02d90e03b864f53114bb7d1'
step_id: 'S239'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unsound closed-value-axis heuristic gate and its hand-maintained exemption classifications; amend the accepted ADR to retain enum typing as an owning command-contract rule without a field-name/sys.modules census.

## Scope

- `Harness closed-value-axis test`
- `accepted MCP closed-value-axis ADR`
- `focused owning command tests`
- `cadence reference`
- `and Step Record.`

## Changes

- `D` `src/cadrumo_harness/mcp/tests/test_closed_value_axis_gate.py`
- `M` `.vault/adr/2026-08-09-mcp-closed-value-axes-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" --basetemp .tmp/pytest-s239 src/cadrumo/entrypoints/cli/tests/test_live_portals_verbs.py src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py` -> `pass`
