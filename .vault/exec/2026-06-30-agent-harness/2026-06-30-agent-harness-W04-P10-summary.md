---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:5c4b674b76f4c54457a832087bb5867a2e5faa8cbddac44b53a17ea7b1451717'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W04.P10` summary

Phase P10 gated the MCP runtime and added determinism replay. All three steps
closed; landed in commit `a422ad49f`.

- Modified: `pyproject.toml`
- Created: `src/aeat/agent/eval/_replay.py`
- Created: `src/aeat/agent/eval/tests/test_tool_call_replay.py`
- Created: `src/aeat/entrypoints/mcp/tests/test_server_refusal.py`

## Description

- S38: `mcp>=1.12,<2` added to the `aeat[agent]` extra; the harness operating data
  still ships in core, the SDK runtime rides the extra.
- S39: `_replay` - determinism-replay over tool calls. Records a golden
  (tool_name, args, invocation) and asserts re-resolution is byte-identical; the
  resolver is injected so the eval layer stays free of the entrypoints import. The
  gate records calls through the real MCP dispatch and proves a tampered record is
  detected as divergent.
- S40: the bare-core refusal contract - `aeat-mcp` (via `emit_missing_sdk_refusal`)
  exits non-zero with the `aeat[agent]` install hint, tested environment-
  independently.

## Outcome

28 MCP + eval tests pass. `pyproject` validates with the `aeat-mcp` script and the
`mcp` runtime in the agent extra.

## Notes

S40 was implemented as an environment-independent refusal-contract test rather
than a bare-wheel `Justfile` lane: the SDK was already installed in this worktree,
so a true bare-core install cannot be staged here. The full bare-wheel
packaging-smoke lane is a product-packaging-campaign follow-up (mirroring the S13
decision). The no-skip project discipline drove the refusal test to assert the
contract directly via `emit_missing_sdk_refusal` instead of skipping when the SDK
is present.
