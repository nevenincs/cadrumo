---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Score observed calls against golden scenarios plus faithfulness and confirmation with the zero-live-submit and zero-handoff-faithfulness invariants

## Scope

- `src/aeat/agent/eval/_live_scoring.py`

## Description

- Author `src/aeat/agent/eval/_live_scoring.py`: score a captured
  `LiveTrajectory` against its golden scenario over OBSERVED calls.
  Dimensions: observed keys resolve; lifecycle order over observed keys;
  expected trajectory covered as an order-preserving SUBSEQUENCE (a live
  model's extra reads are legitimate; a skipped verify or out-of-order
  export is not); per-narration faithfulness against the session's own
  preceding results (advisory-only off-handoff per ADR Q4, hard invariant at
  the handoff); the two ADR-R7 hard invariants (zero live-submit attempts,
  zero handoff faithfulness blocks).
- Injection pattern preserved: the real faithfulness function and the
  live-write/handoff leaf sets are caller-injected; the package never
  imports `entrypoints.mcp`.
- Export the full live surface (harness + scorer) through the eval package
  `__all__`.

## Outcome

Authored by the coordinator. Five-case semantic probe green (grounded
passes; ungrounded non-handoff narration is advisory-only and does NOT fail;
ungrounded handoff narration fails; a live-submit attempt fails hard;
export-before-verify fails lifecycle order). Full `src/aeat/agent` suite
75 passed. Commits `33b3fe6dcf` + a ruff import-order tidy follow-up.

## Notes

None.
