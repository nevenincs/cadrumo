---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S33'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Verify the mcp Python SDK annotation extension surface accepts the anthropic/requiresUserInteraction tool annotation before adopting it (frontier: confirm against the live mcp SDK and official docs)

## Scope

- `src/aeat/entrypoints/mcp/_hitl.py`

## Description

- Verify the mcp Python SDK annotation extension surface against the installed `mcp` 1.28.1 package (not documentation): `mcp.types.Tool` carries `meta: dict[str, Any] | None` (alias `_meta`), the MCP spec's general-purpose extension carrier, with `extra="allow"`.
- Confirm `ToolAnnotations` declares only the camelCase hint fields (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`); the slash-namespaced `anthropic/requiresUserInteraction` key is not a declared `ToolAnnotations` field but a `_meta` prefixed-key vendor extension.
- Round-trip `Tool(_meta={"anthropic/requiresUserInteraction": True})` to confirm it serializes under the `_meta` alias on the wire.
- Add the `anthropic/requiresUserInteraction` `_meta` key constant and a `requires_user_interaction(policy)` derivation helper (True exactly for the `CONFIRM` tier) to `_hitl.py`, so the client-facing interaction flag is a single derived projection of the server's existing confirmation gate.
- Commit `e3b799345e`.

## Outcome

- SDK-surface finding recorded in the commit message with the exact verified file path (`.venv/Lib/site-packages/mcp/types.py`); the carrier is `Tool._meta`, not a `ToolAnnotations` hint field.

## Notes

The plan Step row names `src/aeat/entrypoints/mcp/_annotations.py` as the scoped file; the implementation lands in `src/aeat/entrypoints/mcp/_hitl.py` instead, which already owns the CONFIRM-tier confirmation-policy classification this step derives from. No `_annotations.py` module exists in this package; the deviation is recorded here for traceability. No incidents. No skipped work.
