---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:81e0a4388a21ca89dccffd263eba1b1b8c40b69fbc24257c77355d768a611c6a'
step_id: 'S18'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# GATED (blocked until the mcp-call-latency plan completes): make the MCP server direct dispatch path call gate_refusal() once so a refused call is not composed twice into the envelope

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`

## Description

- Route the direct per-verb call handler through the single shared persona-scope / handoff / permanent-live-write gate `gate_refusal`, replacing the inline `persona_scope_refusal` plus `is_handoff_denied` / `handoff_denial_message` composition in `_call_tool`; `src/cadrumo/entrypoints/mcp/_server.py`.
- Import `gate_refusal` from `_meta_tools` and drop the now-unused `handoff_denial_message` import.
- Add `test_direct_dispatch_gate_composition.py` driving the real server `tools/call` handler: a scope-refused and a handoff-denied verb each compose exactly one refusal, byte-identical to the shared gate, not a doubly-wrapped envelope, and identical to the `execute` meta-path.

## Outcome

Root cause: the direct dispatch path re-derived the scope / handoff / live-write refusal inline, composing the same decision a second time alongside the shared `gate_refusal` the `execute` meta-path already ran. The two compositions were kept in lock-step only by a parity test (a band-aid), and the live-write branch diverged in message text between the paths. The fix makes both entry points resolve the refusal from one `gate_refusal` call, so a refused call carries exactly one refusal and the two surfaces cannot fork.

Behaviour is preserved for every reachable case: `gate_refusal` returns byte-identical scope and handoff messages (proven by the existing parity and handoff tests, still green). The only delta is the permanent-live-write BLOCK message, which is unreachable on the direct path (no live-write tool is ever advertised, so it never resolves through `_call_tool`); after the change the direct path would use the same short BLOCK message the meta-path already uses, making the two paths consistent rather than divergent.

Gates: `pytest src/cadrumo/entrypoints/mcp` gate/identity/dispatch/hitl suites green; CLI `test_json_schema_conformance.py` green (149); ruff and ty clean; `import cadrumo.entrypoints.mcp` clean.

## Notes

There was no runtime double-nesting of a refusal inside another envelope; the "composed twice" was the duplicated composition of the gate decision across the inline direct path and the shared `gate_refusal`. The fix collapses it to one composition site. `persona_scope_refusal` remains defined and exercised by tests as the reference implementation the shared gate is asserted equal to.
