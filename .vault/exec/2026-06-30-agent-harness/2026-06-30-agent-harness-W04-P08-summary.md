---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W04.P08` summary

Phase P08 built the MCP server core. All five steps closed; landed in commit
`a422ad49f`.

- Created: `src/aeat/entrypoints/mcp/__init__.py`
- Created: `src/aeat/entrypoints/mcp/_tools.py`
- Created: `src/aeat/entrypoints/mcp/_dispatch.py`
- Created: `src/aeat/entrypoints/mcp/_annotations.py`
- Created: `src/aeat/entrypoints/mcp/_server.py`
- Modified: `pyproject.toml`

## Description

- S28: MCP entrypoint package with `main()` (the `aeat-mcp` console-script target)
  that lazily loads the SDK and refuses gracefully when absent.
- S29: `build_tool_descriptors` generates the tool list from the Layer 0 manifest
  - one SDK-independent descriptor per operator-callable command (217), skipping
  group-callback help surfaces.
- S30: `_dispatch` maps tool name <-> registry command key (segment-underscore
  safe via the known-key set) and builds the CLI argv (`--format json` at root);
  `_server` dispatches a tool call to the CLI in a subprocess and returns the JSON
  envelope as structured content.
- S31: `_annotations` projects operator mutability onto the MCP
  readOnly/destructive/idempotent hints; the descriptor carries them.
- S32: the `aeat-mcp` console script bound to `aeat.entrypoints.mcp:main`.

## Outcome

The tool surface builds (217 tools, all `aeat_*`, no `root.*`, contract read-only,
ledger.remove destructive). The descriptor-to-SDK-Tool adaptation is verified
against the real installed MCP SDK types.

## Notes

The MCP SDK (`mcp` 1.28.1) was already present in the worktree venv (a transitive
dependency), so the SDK-adaptation path is exercised live; the lazy import and
graceful-refusal contract still hold for a bare-core install.
