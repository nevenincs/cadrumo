---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:52c0bc34003cde148f890261714b9e99436e1f140951c64f338e0c49afe4756e'
step_id: 'S45'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-100 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-100/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-100` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `entity_type` equals `natural_person` (annual IRPF Renta filer).

## Outcome

`preparar-modelo-100` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
