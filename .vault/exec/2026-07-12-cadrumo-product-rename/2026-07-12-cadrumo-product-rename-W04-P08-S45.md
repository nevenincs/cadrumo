---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S45'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename MCP prompts and product-facing tool copy

## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py`

## Description

- Rename the orientation prompt, title, and operating brief to Cadrumo.
- Delegate embedded prompt URI construction to the canonical MCP resource helper.
- Preserve AEAT wording only where it denotes the Spanish tax authority or its period codes.
- Prove Cadrumo prompt names, copy, and embedded resource URIs through the real prompt and server surfaces.

## Outcome

MCP guided prompts now expose one Cadrumo product identity and use the
`cadrumo://` resource contract without a duplicate URI scheme authority.
Focused Ruff checks and all ten MCP prompt integration tests pass.

## Notes

The two prompt-test URI expectations originated with the concurrent S44
resource-scheme change. The S44 owner confirmed `resource_uri` as the final
constructor and explicitly transferred those cohesive assertions to S45; no
changes were made to `_resources.py` in this step.
