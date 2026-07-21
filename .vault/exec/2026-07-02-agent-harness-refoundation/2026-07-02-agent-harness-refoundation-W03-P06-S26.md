---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S26'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add tests for the faithfulness serving path, the handoff deny rules, and telemetry

## Scope

- `src/aeat/entrypoints/mcp/tests/test_serving_gates.py`

## Description

- Add `test_serving_gates.py` driving the real server in-process through the SDK memory transport against `build_server`'s handlers.
- Assert the handoff leaves are absent from the preparer and reconciler tools list but present for the verifier, and a direct denied handoff call refuses with the persona-and-owner denial message.
- Assert arguments-faithfulness blocks an ungrounded amount at a handoff verb (single advisory content block, before dispatch) and advises without blocking on a non-handoff verb (two content blocks: advisory then envelope).
- Exercise the grounding window making a previously-returned figure pass and blocking an empty window at the handoff boundary through the real serving-path gate functions.
- Inject a tmp-path telemetry writer and assert the raw session file carries content hashes but neither the amount argument nor the result payload.
- Assert the meta-execute path fail-closes a handoff-tier CONFIRM.

## Outcome

Seven real-behavior tests pass, all against the real MCP client-server pair (no mocks) for the short-circuiting gates, and against the exact serving-path gate functions `build_server` calls for the post-dispatch semantics. The persona handoff-deny boundary, the handoff faithfulness block, the non-handoff advisory, the grounding-window pass, payload-free telemetry, and the meta fail-close are all covered. Ruff check/format clean.

## Notes

Two serving-path assertions cannot run over a full in-process CLI dispatch because every verb except the bootstrap-exempt `contract` resolves the encrypted secret store at CLI startup, which the spawned `aeat` subprocess cannot reach in a focused gate test without provisioning a profile, secret passphrase, and work-unit lifecycle. The advisory-does-not-block property and the grounding-window pass are therefore exercised against `SessionGroundingWindow` and `arguments_faithfulness` directly - the exact functions the server handler calls - which keeps them real-behavior without fabricating storage. The telemetry payload-free proof still runs over a real dispatch: `contract` succeeds and a handoff faithfulness block records the amount-bearing arguments as a hash, so the raw file is verified to hold a 64-hex digest but neither the `500.00` argument nor the contract envelope text. The amount token uses the `NNN.NN` shape the matcher recognises; a four-digit undelimited integer is intentionally not amount-shaped and would not exercise the gate.
