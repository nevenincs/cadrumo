---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:c0a9055e2839f7cc441a84f0098d22de67019f10e37318b8a35b71185dda4c88'
step_id: 'S26'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Emit the plugin .mcp.json declaring the stdio aeat-mcp server launched via uvx aeat at a pinned version with AEAT_MCP_PERSONA wired from the userConfig persona interpolation

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to emit the plugin `.mcp.json`, declaring the stdio `aeat-mcp` server launched via `uvx --from aeat==<version> aeat-mcp` at a pinned version.
- Wire `AEAT_MCP_PERSONA` from the `${user_config.persona}` interpolation so the persona selected in the client's `userConfig` reaches the launched server.
- Landed together with `S25` and `S27` in one commit because the three facets (agents tree, `.mcp.json`, `userConfig` persona option) co-build one emission function in one file, and the plan lists them as sequential same-file Steps.
- Commit `ccb13180be`.

## Outcome

- The emitted `.mcp.json` launches `aeat-mcp` at a pinned version with the persona sourced from user configuration, never hardcoded.

## Notes

No incidents. No skipped work.
