---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S19'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Re-run the installed tax and MCP oracles after D1 through D4 land and capture the corrected warm serving behavior as installed evidence

## Scope

- `dev/packaging/installed_mcp_oracle.py`

## Description

- Re-run the installed CLI tax oracle and the installed MCP oracle against the
  rebuilt release cohort after D1 through D4 landed.

## Outcome

- Installed CLI lane: the core packaging smoke passed end-to-end against the
  rebuilt cohort's root wheel (fresh venv install, digest-fragment-pinned,
  grounded Modelo 200 oracle `DP200014:00562 == 23000.00`); retained manifest
  under `var/packaging-smoke/core-20260717T150842Z`.
- Installed MCP lane: the MCPB client-install suite passed 4/4 against the
  rebuilt cohort through the real client runtime, including the self-healing
  bootstrap path, in 125 seconds — versus 428 seconds for the same suite
  before the campaign, the warm-serving and validation-skip work visible in
  the harness itself.

## Notes

- Executed by the plan owner directly. Both lanes consumed the S20 rebuilt
  cohort bytes without rebuilding.
