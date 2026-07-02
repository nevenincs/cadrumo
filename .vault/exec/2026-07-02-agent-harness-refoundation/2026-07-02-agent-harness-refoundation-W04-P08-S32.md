---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S32'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the local measurement report artefact

## Scope

- `src/aeat/agent/eval/_report.py`

## Description

- Author the measurement report: aggregate LiveScenarioScores + trajectories into one typed artefact and its markdown render — scenarios run/passed per persona, the two hard invariants' observed totals (both must be zero), tool-error and unfaithful-narration tallies, per-scenario failure reasons. Pure aggregation, no payloads.

## Outcome

Authored by the coordinator. Probe green; ruff clean. Commit shared by
S31+S32 (one cohesive flywheel+report landing).

## Notes

None.
