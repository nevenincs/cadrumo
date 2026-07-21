---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S49'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update generator tests for plugins/cadrumo and pinned Cadrumo launcher output

## Scope

- `src/cadrumo/agent/tests`

## Description

- Retarget plugin and marketplace generator tests to the `cadrumo` plugin identity and `./plugins/cadrumo` source.
- Pin the emitted MCP launch contract to `uvx --from cadrumo[agent]==<version> cadrumo-mcp` with Cadrumo environment keys.
- Reject former `plugins/aeat`, `aeat` MCP server, `aeat-cli`, `aeat-mcp`, and former launcher copy in generated output.

## Outcome

The real filesystem materialisers now prove the canonical Cadrumo plugin tree,
manifest identity, distribution pin, console script, environment interpolation,
and product copy without accepting former product paths or commands.

## Notes

- Thirteen focused generator tests passed after S48 and its launcher-copy correction landed; Ruff and formatting passed.
- The checked-in marketplace scaffold parity test is deliberately outside this run because S50 owns regeneration of that generated output.
