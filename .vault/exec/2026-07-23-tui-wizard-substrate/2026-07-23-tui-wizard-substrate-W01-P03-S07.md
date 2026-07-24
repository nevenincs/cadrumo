---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S07'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Implement the immutable FlowState and the pure transition engine (answer, next, back, jump, reset, restart) with per-transition visibility recompute and staleness marking

## Scope

- `src/cadrumo/application/flows/_engine.py`

## Description

- Implement the immutable FlowState and pure transitions (answer, next, back, jump, reset, restart, set_instance_count) with per-transition visibility recompute, gating-change staleness, repeating-group instance keying and shrink-orphan staleness, and section-exit blocking.
- Land in commit 91c5e51afc; immutability convention documented in 9b03c2180d.

## Outcome

Engine is the single flow authority; frontends dispatch transitions only (reviewer invariant 1 PASS).

## Notes

Stale marks never delete answers; deferral never resolves silently (reviewer invariant 2 PASS).
