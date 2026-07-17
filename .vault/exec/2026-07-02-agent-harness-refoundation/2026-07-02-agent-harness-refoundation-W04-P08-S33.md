---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S33'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the live-harness test

## Scope

- `src/aeat/agent/eval/tests/test_live_harness.py`

## Description

- Add `test_live_harness.py` capturing one real scripted-persona session against the real server over stdio and scoring it against the golden scenario.
- Inject the real `faithfulness_check` from `entrypoints.mcp` and the live-write / handoff leaf sets from their single `_hitl` declarations, per the scorer's hexagonal injection contract.
- Exercise the five scorer semantics over constructed trajectories fed to the real scorer: a grounded trajectory passes; an ungrounded figure at a non-handoff step is advisory-only and still passes; the same figure at the export handoff boundary fails the hard invariant; an observed live-write leaf fails; and export-before-verify fails the lifecycle order.

## Outcome

Six real-behavior tests pass. The captured real session (one floor-tool call over stdio) is scored and correctly reported as not covering the scenario's expected trajectory, proving the capture-to-score pipeline end to end. The five scorer semantics hold against the real judging logic. Ruff check/format clean.

## Notes

The five semantics are exercised over constructed `LiveTrajectory` inputs fed to the real `score_live_trajectory` - real judging logic with test-data inputs, not a mocked scorer - because the pathological trajectories (a live-submit attempt against a console that exposes no submit tool, an export ordered before verify) cannot be produced by a real session and must be supplied as data. The live-write leaf set is imported as `_LIVE_WRITE_LEAVES` from `_hitl` because that private frozenset is its single declaration and the scorer's design explicitly injects it from the server layer the eval package must not import; the test is the sanctioned injection seam.
