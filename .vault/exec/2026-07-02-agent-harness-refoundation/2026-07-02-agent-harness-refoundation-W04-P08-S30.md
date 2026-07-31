---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:bc6e1f8c0adba0f75abfe34cbee94113cbda94f10812f6a8b1a13cb9888b98d2'
step_id: 'S30'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Extend the golden-scenario models for live-persona trajectory capture and scoring

## Scope

- `src/aeat/agent/eval/_models.py`

## Description

- Extend `src/aeat/agent/eval/_models.py` with the live-persona capture
  types in the module's strict-frozen style: `LiveToolCallRecord` (tool
  name, caller-mapped command key, canonical arguments JSON, isError, result
  text, duration), `LiveNarrationRecord`, `LiveElicitationRecord` +
  `ElicitationAction`, `LiveTrajectory` (with the
  `observed_command_keys` projection the key-sequence dimensions consume),
  and `LiveInvariantVerdict` (the two ADR-R7 hard invariants: zero
  live-submit attempts, zero handoff faithfulness blocks).
- Re-export through the eval package `__all__`.

## Outcome

Authored by the coordinator. Ruff clean; smoke-validated construction and
projection. Commit `08e944e59`.

## Notes

The commit absorbed a peer's uncommitted content-neutral reformat (a
ruff-style line-join in `UnderDeclarationVerdict.passed`) present in the
working tree — preserved rather than stranded, per the shared-worktree
preserve discipline.
