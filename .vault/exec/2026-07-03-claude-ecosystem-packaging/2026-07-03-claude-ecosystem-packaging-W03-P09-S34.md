---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:b14acc45664706d1de34b9b4bfd93d2e5cf7a7594865b7582e806a18b1461c07'
step_id: 'S34'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add the anthropic/requiresUserInteraction annotation to CONFIRM-tier (state-mutating) MCP tools alongside the existing destructiveHint matrix

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Stamp `_meta={"anthropic/requiresUserInteraction": true}` on every SDK tool `build_sdk_tools` emits whose `confirmation_for_tool(...)` resolves to `ConfirmationPolicy.CONFIRM`.
- Derive the stamped set from the existing single-authority mutability classification; no hand-listed tool names.
- Leave every non-CONFIRM tool without a `_meta` entry, alongside the existing `destructiveHint` matrix.
- Commit `f178141b73`.

## Outcome

- `src/aeat/entrypoints/mcp/_server.py` changed by 14 insertions / 1 deletion, wiring the `requires_user_interaction(policy)` helper from `S33` into tool construction.

## Notes

The plan Step row names `src/aeat/entrypoints/mcp/_annotations.py` as the scoped file; the implementation lands in `src/aeat/entrypoints/mcp/_server.py`, the module that already owns `build_sdk_tools` and the existing `destructiveHint` annotation matrix this step extends. No incidents. No skipped work.
