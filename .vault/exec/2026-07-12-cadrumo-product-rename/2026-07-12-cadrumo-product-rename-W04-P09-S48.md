---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S48'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename plugin identity, distribution pin, command, source path, metadata, and environment interpolation

## Scope

- `src/cadrumo/agent/_workspace.py`

## Description

- Derive plugin, MCP, distribution, source-path, and product environment identities from `PRODUCT_IDENTITY`.
- Rename plugin and marketplace metadata to Cadrumo while preserving AEAT authority language.
- Remove former product names from generated MCP configuration and operator-workspace copy.

## Outcome

The plugin generator now emits the `cadrumo` plugin at `plugins/cadrumo`, pins
`cadrumo[agent]`, launches `cadrumo-mcp`, and configures the `cadrumo` MCP
server with `CADRUMO_MCP_PERSONA` and `CADRUMO_MCP_SURFACE`. Product-owned
metadata names Cadrumo; AEAT remains only where it denotes the tax authority,
its legal corpus, and filing boundary, while lowercase `aeat` remains the sole
human executable under the accepted CLI-executable decision.

## Notes

Ruff formatting, Ruff lint, Python compilation, scoped residue search, and
whitespace validation passed. Generated marketplace output and generator tests
remain owned by S50 and S49 respectively and were not changed here.
Formal review corrected operator copy that had initially treated the Cadrumo
product name as the human executable instead of preserving the canonical
lowercase `aeat` command.
