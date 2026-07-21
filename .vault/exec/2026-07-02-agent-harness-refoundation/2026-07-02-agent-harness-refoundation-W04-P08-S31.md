---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S31'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add the flywheel that promotes live failures into new golden scenarios

## Scope

- `src/aeat/agent/eval/_flywheel.py`

## Description

- Author the flywheel: promote a live failure into a golden regression scenario. Conservative by design — the promoted TOML re-declares the ORIGINAL correct expectations while the observed failing trajectory and reasons ride as comment-header evidence for the annotation queue; a failure never becomes the new normal. Content-addressed names make re-promotion idempotent; a passing run refuses promotion. Probe proves the promoted file round-trips through load_scenario.

## Outcome

Authored by the coordinator. Probe green; ruff clean. Commit shared by
S31+S32 (one cohesive flywheel+report landing).

## Notes

None.
