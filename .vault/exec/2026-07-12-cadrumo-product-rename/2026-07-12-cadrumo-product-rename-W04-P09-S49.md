---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
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

## Contextual-casing continuation

The generator contract tests now distinguish product identity fields from
sentence prose explicitly. They require `CADRUMO` in plugin display and
author/marketplace-owner identity fields, while requiring `Cadrumo` in the
plugin and marketplace sentence descriptions. Existing assertions continue to
pin the lowercase `cadrumo` plugin, server, distribution, and source identities,
the `cadrumo-mcp` executable, and `CADRUMO_MCP_*` interpolation keys.

Thirteen focused real-filesystem generator tests passed, including live strict
plugin and marketplace validation with Claude CLI 2.1.207. Ruff lint and format
checks passed for both test modules. The checked-in scaffold parity assertion
remains intentionally assigned to S50 regeneration and was not used to close
this test-authority Step.
