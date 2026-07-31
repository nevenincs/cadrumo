---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:45a4e0378d679b6000965e8ee680e0c685b33844d87501ae20831612c147d91c'
step_id: 'S59'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-353 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-353/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-353` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `iva.group_dominant_entity_enrolled` is true.

## Outcome

`preparar-modelo-353` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
