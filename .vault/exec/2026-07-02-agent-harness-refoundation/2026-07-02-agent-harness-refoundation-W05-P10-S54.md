---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S54'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-202 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-202/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-202` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `entity_type` equals `legal_entity`.

## Outcome

`preparar-modelo-202` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
