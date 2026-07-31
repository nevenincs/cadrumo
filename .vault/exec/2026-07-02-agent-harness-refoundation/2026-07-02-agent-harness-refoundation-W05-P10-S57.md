---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:cb2086a328d0e05e586d83f79f0958c344528674f62d9d353f099dc38b8b50ec'
step_id: 'S57'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-322 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-322/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-322` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `iva.group_member_enrolled` is true.

## Outcome

`preparar-modelo-322` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
