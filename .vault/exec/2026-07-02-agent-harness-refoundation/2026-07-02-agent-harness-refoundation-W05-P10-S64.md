---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S64'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the retenedor-empleador selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/retenedor-empleador/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `retenedor-empleador` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts (any): `has_employees`, `pays_professionals_with_retencion`, or `pays_rent_with_retencion` is true.

## Outcome

`retenedor-empleador` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

The prose lists three disjunctive withholding triggers; encoded with profile_match `any`.
