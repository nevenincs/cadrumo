---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
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
- Invoke the sole installed human `aeat` CLI from supervised MCP subprocess calls.
- Retarget timeout guidance and server-owned meta-tool descriptions to sentence-prose `Cadrumo`.
- Preserve AEAT live-write, authority adapter, and legal language, consume S44's completed resource-scheme result, and defer broad tool-prefix budgets to S46.
- Exercise the server identity, product-facing meta-tool copy, and a real end-to-end subprocess-backed `contract` meta-execution.
- Derive the protocol server name from `PRODUCT_IDENTITY.mcp_server` and make the focused contract test assert that authority relationship instead of duplicating its current literal value.

## Outcome

The server initializes with the lowercase machine identifier `cadrumo`, while
supervised verb calls execute `PRODUCT_IDENTITY.cli_executable`, exactly `aeat`.
Server-owned product prose says `Cadrumo`; `AEAT` remains only for the Spanish
tax authority and the permanent live-write prohibition. The existing
`CADRUMO_MCP_PERSONA` and `CADRUMO_MCP_SURFACE` environment contracts remain
canonical product controls.

The focused suite passes the real MCP SDK server-name and capability checks,
exact meta-tool copy assertions, and the end-to-end subprocess-backed
`contract` meta-execution. That real execution reaches the installed `aeat`
command; it does not rely on a runner fake or a `cadrumo` executable alias.

## Notes

- The active environment exposes `aeat` as the human CLI and no `cadrumo`
  executable. The subprocess test passes against that binding directly.
- Eighteen focused MCP integration tests pass against the real SDK with project
  addopts cleared so the direct module is actually collected. Ruff, formatting,
  and Ty pass on the focused server and test surface; the resource-kind
  annotation and optional SDK-description narrowing now express the existing
  runtime contracts without ignores.
- Server-owned resource documentation now reflects S44's completed `cadrumo://` scheme. Retained AEAT live-write wording and outbound-adapter paths identify the Spanish tax authority and are not product aliases.
- Broad per-verb tool prefixes live in `_dispatch.py` and the MCP test budgets assigned to S46, outside this Step.
- This remediation cross-carries a concurrent mechanical removal of generated scaffold comments from this record; no peer-authored evidence prose was removed or rewritten.
