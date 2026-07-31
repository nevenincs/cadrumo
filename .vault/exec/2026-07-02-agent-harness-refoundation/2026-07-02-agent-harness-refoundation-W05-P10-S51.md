---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:52016e0f1491c5e531df3cc0021d4935841b19e6bfa0c28d726710d104dcae1d'
step_id: 'S51'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-190 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-190/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-190` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts (any): `has_employees` or `pays_professionals_with_retencion` is true (annual summary of the quarterly Modelo 111).

## Outcome

`preparar-modelo-190` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
