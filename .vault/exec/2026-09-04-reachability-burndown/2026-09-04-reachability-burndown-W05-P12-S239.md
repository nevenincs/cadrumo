---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7c6db540cef03299bdba01194a998c5578cf4160a8adcec5e422edd0ad3238c1'
step_id: 'S239'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
