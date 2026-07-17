---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W04.P09` summary

Phase P09 enforced the HITL tiers and the faithfulness check. All five steps
closed; landed in commit `a422ad49f`.

- Created: `src/aeat/entrypoints/mcp/_hitl.py`
- Created: `src/aeat/entrypoints/mcp/_faithfulness.py`
- Created: `src/aeat/entrypoints/mcp/tests/test_hitl_and_live_write.py`
- Created: `src/aeat/entrypoints/mcp/tests/test_faithfulness.py`
- Created: `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`

## Description

- S33: `_hitl` PreToolUse policy - auto-approve reads and non-destructive
  mutations, confirm destructive and filing-handoff (export/file) verbs, block any
  forbidden AEAT live-write.
- S34: `_faithfulness` PostToolUse check - flags amount-shaped numbers in the
  agent narration absent from the tool JSON; advisory by default, blocking on the
  handoff path; bare integers (casilla numbers, years) are not flagged.
- S35: the never-expose-live-write test - no exposed tool resolves to BLOCK, and a
  synthetic live-write verb is proven to block (the rail is non-vacuous).
- S36: the HITL tier behaviour test - read-only auto, destructive/handoff confirm.
- S37: the faithfulness behaviour test - grounded narration passes, a fabricated
  amount is flagged advisory and blocks at handoff.

## Outcome

All HITL and faithfulness tests pass. The BLOCK rail is enforced server-side
(call_tool refuses a blocked tool); the CONFIRM tier is surfaced via the SDK
annotations the client reads; faithfulness is a hook function the harness applies
to agent narration.

## Notes

PreToolUse confirmation and PostToolUse faithfulness are exposed as pure functions
(`confirmation_for_tool`, `faithfulness_check`) for the Agent-SDK hook layer; the
MCP server itself enforces only the forbidden-live-write block, since it does not
see the agent's narration.
