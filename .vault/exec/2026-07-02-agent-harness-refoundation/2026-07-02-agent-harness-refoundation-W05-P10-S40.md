---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S40'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the autonomo-modulos selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/autonomo-modulos/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `autonomo-modulos` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts (all): `irpf_income_categories` contains `actividad_economica` AND `irpf_estimation_regime` equals `objetiva`.

## Outcome

`autonomo-modulos` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
