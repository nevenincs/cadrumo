---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S03'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Author the strict frozen FlowDefinition family (flow, section, page, choice, copy-reference, branching predicate, repeating group, compare-select) with build-time validators for unique ids, forward-only references, and reference-not-literal copy slots

## Scope

- `src/cadrumo/application/flows/_definition.py`

## Description

- Author the strict frozen FlowDefinition family (flow, section, page, choice, copy reference, condition/visibility, repeating group) with build-time validators: unique ids, forward-only gate references, choice-widget coherence, compare-select provenance, reserved defer token, count-source typing, per-mode checkpoint coverage.
- Land in commit 91c5e51afc; fingerprint docstring corrected in 9b03c2180d.

## Outcome

Definition contract enforced at model construction; the real 11-section setup catalogue validates through it.

## Notes

Copy slots are references only; literal prose is structurally unrepresentable.
