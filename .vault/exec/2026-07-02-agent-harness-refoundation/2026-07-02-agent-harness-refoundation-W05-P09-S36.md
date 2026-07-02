---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S36'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---




# Add the applies_when coverage gate asserting every skill declares a structured predicate

## Scope

- `src/aeat/agent/tests/test_skill_applies_when.py`

## Description

- Add `test_skill_applies_when.py`: assert every shipped skill enumerates through the validating `iter_skill_metadata` loader (missing/malformed/invalid predicates fail loudly), one validated metadata per shipped SKILL.md.
- Assert every predicate declares at least one axis and every profile fact names a real `TaxpayerProfile` field.
- Add an anti-tautology proof: a bogus fact name and an empty predicate are both rejected, so the gate can fail.

## Outcome

The coverage gate is green after the P10 lifts: all 28 skills declare a valid structured `applies_when`. Before the lifts the three coverage assertions correctly red while the anti-tautology proof passed, confirming the gate has teeth.

## Notes

Per the plan sequencing, this gate reds between its own landing (S36) and the completion of the P10 lifts (S64); it is closed only now that the lifts are in and the gate passes.
