---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Register the prompts and resources server capabilities on the stdio server

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Extract the SDK-runtime server construction from the stdio runner into a testable `build_server`, so handler registration and capability negotiation are unit-tested without the transport.
- Register empty-but-valid `list_prompts` / `get_prompt` / `list_resources` / `read_resource` handlers so the server advertises the prompts and resources capabilities now; W02 populates the bodies.
- Advertise the `search` and `execute` meta-tools alongside the per-verb tools via `build_meta_sdk_tools`, and route their calls in `call_tool` through `search_commands` and `meta_execute` so the long-tail surface is reachable and `execute` runs through the same gates as a direct call.
- Reduce the stdio runner to building the server and running the transport.

## Outcome

`build_server` returns a server whose negotiated capabilities advertise tools, prompts, and resources; the two meta-tools are exposed with valid input schemas; and the direct per-verb call path, persona scope, and live-write block are preserved unchanged. Ruff check/format clean, pyright clean, and the mcp suite is green at 61 passed with the full W01 wave gate (mcp plus rule-surface conformance) green at 75 passed.

## Notes

The prompt and resource handler bodies are intentionally minimal: `list` returns an empty sequence and `get` / `read` raise not-found. Registering the handlers is what triggers capability negotiation; the empty bodies are the valid floor until W02 supplies the operating-layer documents. The meta-tools are advertised unconditionally (never persona-scoped away) because `execute` applies the persona gate internally, so scoping the meta-tool itself would be redundant and would hide the fallback from a scoped session that legitimately needs it.
