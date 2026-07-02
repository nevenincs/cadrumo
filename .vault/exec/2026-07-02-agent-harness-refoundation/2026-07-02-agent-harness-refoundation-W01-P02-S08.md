---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add tests for the meta-tool fallback and capability registration

## Scope

- `src/aeat/entrypoints/mcp/tests/test_meta_tools.py`

## Description

- Add `test_meta_tools.py` covering search relevance, gate parity, meta-execute control flow, the meta-tool SDK surface, and server capability registration.
- Assert `search` ranks a named verb above one that merely mentions the query and surfaces mutability hints, and that an empty query matches nothing.
- Prove `gate_refusal` returns byte-identical refusals to the direct `persona_scope_refusal` for every scoped refusal under a persona, and blocks a synthetic live-write leaf.
- Prove `meta_execute` never reaches its runner on a blocked or unknown command and dispatches a read-only command (`contract`) end to end through the real subprocess runner.
- Assert the two meta-tools expose valid input schemas and that `build_server` advertises tools, prompts, and resources capabilities.

## Outcome

Eight real-behavior tests pass, including an end-to-end `contract` dispatch through the genuine subprocess runner and a capability-negotiation assertion against the real MCP SDK. The full W01 wave gate (mcp suite plus rule-surface conformance) is green at 75 passed. Ruff check/format clean.

## Notes

The injected `run` callable is the server's real dependency-injection seam, not a service double: meta-execute is pure control-flow logic over an external subprocess dependency, so isolating the flow with an injected runner (and a real runner for the end-to-end case) is unit isolation permitted by the testing mandate, while the subprocess path itself is exercised for real in the read-only dispatch test and will be exercised again by the W04 handshake floor.
