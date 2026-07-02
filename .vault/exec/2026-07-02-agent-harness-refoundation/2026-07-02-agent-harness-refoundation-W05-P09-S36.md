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

- Add `test_skill_applies_when.py`: the coverage gate is the strict presence enforcer - it asserts every shipped skill declares a structured `applies_when` (a skill whose predicate is `None` fails), one metadata per shipped SKILL.md, no skill silently skipped.
- Assert every declared predicate names at least one axis and every profile fact resolves to a real `TaxpayerProfile` field.
- Add an anti-tautology proof: a bogus fact name and an empty predicate are both rejected at parse, so the gate can fail.

## Outcome

The gate is authored and correct, and enforces presence at the corpus level (distinct from the load path, which tolerates a missing predicate). It currently PASSES because the 28 P10 lifts were already committed before the scope cut; it would red the moment any skill ships without the field.

## Notes

SCOPE CUT (operator directive, 2026-07-02): P10 predicate-lift authoring under `src/aeat/_data/agent/skills/` is coordinator-owned, not mine. This step is therefore left OPEN for the coordinator to close after they own the lifts, even though the gate currently passes against my already-committed lifts. Honest status: the gate is GREEN now (not red) because the lifts landed before the scope cut; the coordinator may adopt those commits or re-author, and closes S36 when the corpus is theirs and the gate passes.

COORDINATOR RATIFICATION (2026-07-02): the coordinator personally reviewed
all 28 lifted predicates against each skill's prose, the live
`TaxpayerProfile` fields, and the tax semantics (the M309 predicate — the
no-periodic-303 regime set — and the disjunctive withholding gates were the
decisive quality checks) and ADOPTS the executor's lifts without change.
The 34-skill corpus (28 lifts + the six coordinator-authored WHEN skills of
P11) passes this gate, the rule-surface drift gate, and the golden sweep.
S36 is closed on that ratified, coordinator-owned corpus.
