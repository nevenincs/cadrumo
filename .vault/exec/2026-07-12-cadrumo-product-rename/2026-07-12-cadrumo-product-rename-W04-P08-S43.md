---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S43'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename server, tool prefixes, subprocess argv, and product environment names while retaining authority language

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`
- `src/cadrumo/entrypoints/mcp/tests/test_meta_tools.py`

## Description

- Rename the MCP protocol server identity from the former product spelling to `cadrumo`.
- Invoke the sole installed `cadrumo` CLI from supervised MCP subprocess calls.
- Retarget timeout guidance and server-owned meta-tool descriptions to Cadrumo.
- Preserve AEAT live-write, authority adapter, and legal language, consume S44's completed resource-scheme result, and defer broad tool-prefix budgets to S46.
- Exercise the server identity, product-facing meta-tool copy, and a real end-to-end subprocess-backed `contract` meta-execution.

## Outcome

The server now initializes as `cadrumo`, supervised verb calls execute the
installed `cadrumo` command, and all product-facing copy owned by this module
names Cadrumo. The existing `CADRUMO_MCP_PERSONA` and surface environment
contracts were already canonical and remain unchanged.

The focused clean-environment suite passed three tests, including a real CLI
subprocess and exact server/copy assertions.

## Notes

- The shared worktree temporarily exposed only an `aeat` script through peer metadata, so the first real subprocess test could not locate `cadrumo`. The same test passed in a clean canonical Cadrumo clone with the two owned files overlaid; no shared metadata was changed.
- Server-owned resource documentation now reflects S44's completed `cadrumo://` scheme. Retained AEAT live-write wording and outbound-adapter paths identify the Spanish tax authority and are not product aliases.
- Broad per-verb tool prefixes live in `_dispatch.py` and the MCP test budgets assigned to S46, outside this Step.
