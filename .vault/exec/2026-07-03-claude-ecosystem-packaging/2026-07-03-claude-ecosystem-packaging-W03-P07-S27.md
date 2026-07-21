---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S27'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Declare the userConfig persona string option with a default in the plugin manifest, keeping server-side validation as the refusal surface

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to declare the `userConfig` persona string option on the plugin manifest with a default of `""`.
- Keep server-side validation (the MCP server's own persona gate) as the sole refusal surface for an invalid persona; the manifest option only exposes the client-facing configuration point.
- Landed together with `S25` and `S26` in one commit because the three facets (agents tree, `.mcp.json`, `userConfig` persona option) co-build one emission function in one file, and the plan lists them as sequential same-file Steps.
- Commit `ccb13180be`.

## Outcome

- `plugin.json` declares a `userConfig.persona` string option with an empty-string default; no client-side persona validation duplicates the server gate.

## Notes

No incidents. No skipped work.
