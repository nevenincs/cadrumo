---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ca23c45904cbed480886ca909cb39d15690f7a7d524d9d4784f1ea40ccc34854'
step_id: 'S69'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Author the resumen-anual skill sequencing the annual-window obligations

## Scope

- `src/aeat/_data/agent/skills/resumen-anual/SKILL.md`

## Description

- Author the resumen-anual WHEN-layer skill: temporal_trigger annual_window; reconciliation-first framing (annual summaries must agree with filed quarters), stop-on-divergence with routing to rectificar-declaracion, unfiled quarters to regularizar-atrasos first.

## Outcome

Authored by the coordinator per the operator directive that all skill content
is coordinator-authored. Gates green at commit: rule-surface conformance,
skill applies_when validation, and the all-scenario golden sweep (24 passed
across the six new skills/scenarios). Commit `c85655d63`, exactly one file.

## Notes

None.
