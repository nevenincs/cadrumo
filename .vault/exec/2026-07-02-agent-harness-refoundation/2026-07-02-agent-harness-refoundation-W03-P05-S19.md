---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the elicitation module with the capability-degradation matrix over accept, decline, and cancel, a destructiveHint fallback, and a default handoff refusal when elicitation is absent

## Scope

- `src/aeat/entrypoints/mcp/_elicitation.py`

## Description

- Author `src/aeat/entrypoints/mcp/_elicitation.py` as SDK-independent pure
  logic in the `_hitl` style: the capability-degradation matrix
  (`resolve_confirm_route`), the minimal one-boolean elicitation payload
  (`confirmation_request` — no argument values or taxpayer data ever ride
  in it, per the MCP-spec prohibition on eliciting sensitive information),
  the fail-closed result mapping (`decision_from_elicitation`), and the
  instructive refusal texts.
- Matrix as decided in ADR R6: BLOCK always refuses; CONFIRM elicits when the
  client negotiated elicitation; without elicitation a handoff-tier verb
  (export/file) refuses by default with a route-to-a-capable-client message,
  while a non-handoff destructive verb proceeds under the client's
  destructiveHint confirmation UI.
- Fail-closed on every non-explicit-yes path: decline, cancel, malformed
  accept, and accepted `confirm: false` all refuse.

## Outcome

Authored by the coordinator (gate semantics are a hard technical challenge
under the operator directive). Matrix and fail-closed behavior verified by
inline probes at commit; ruff clean. Commit `e27e88de7`, exactly one file.
Server wiring (S20) follows once the W02 executor's `_server.py` edits land
— both waves share that file and W02 holds it now.

## Notes

None.
