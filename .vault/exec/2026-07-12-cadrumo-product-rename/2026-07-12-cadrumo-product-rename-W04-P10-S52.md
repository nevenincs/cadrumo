---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S52'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename the secondary bundle manifest identity and executable

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Rename the secondary bundle identity, display copy, author, and keywords to Cadrumo.
- Hard-cut the MCP entry point and command to `cadrumo-mcp`, the product environment to `CADRUMO_MCP_PERSONA`, and product tools to `cadrumo_*` names.
- Retain AEAT only where it identifies the tax authority, BOE/AEAT legal corpus, or authority search keyword.

## Outcome

The secondary MCP bundle manifest now presents only the Cadrumo product identity
and executable contract, with no former command, tool alias, or fallback.

## Notes

- The real project manifest checker reported `manifest.json valid: cadrumo 0.1.0`.
- Two manifest-focused MCPB build tests passed; five later build/signing tests were outside S52 scope.
- Formal review against the committed product rename ADR found no issues.
