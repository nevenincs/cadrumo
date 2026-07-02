---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S42'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the exportar-declaracion selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/exportar-declaracion/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `exportar-declaracion` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: workflow_phase `export` - the after-calculate, before-file helper.

## Outcome

`exportar-declaracion` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
