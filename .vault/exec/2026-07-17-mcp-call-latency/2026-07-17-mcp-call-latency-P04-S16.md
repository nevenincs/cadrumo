---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S16'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Prove CLI-versus-MCP envelope parity with a real-behavior oracle asserting byte-identical envelopes across the subprocess and in-process transports so D4 does not fork result shapes

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py`

## Description

- Add `test_inprocess_envelope_parity.py`: a real-behavior oracle running the same verb with the same arguments through both real transports - a genuine `aeat` subprocess (`_run_subprocess_tool`) and the warm in-process runtime (`_run_inprocess_tool`) - and asserting the emitted envelopes are byte-for-byte identical after canonical JSON serialisation.
- Cover the stdout success document with a read verb needing no active profile (`contract`).
- Cover the stderr error document with a verb that refuses with no active profile (`review.queue`), so parity holds on the error boundary path too.

## Outcome

Both transports emit byte-identical envelopes. The success envelope (`contract`) and the refusal envelope (`review.queue`, rendered by the CLI error boundary to stderr) match exactly across the subprocess and warm in-process transports - D4 does not fork the result shape. Two tests pass against the real registry and filesystem, no mocks.

## Notes

The Cadrumo envelope carries no per-run fields (the error document's `trace_id` is null, not a per-call token), so the whole envelope is compared rather than an excluded subset; the test documents that a future per-run field would be excluded by name with a stated reason rather than the comparison being loosened. `overview.status` was rejected as the refusal probe because it renders a success landing card without a profile; `review.queue` refuses cleanly.
