---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:cd9d0dfd150c625a170f794824acdda336c7265e232db60b7f054226338184f3'
step_id: 'S41'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the clasificar selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/clasificar/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `clasificar` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: workflow_phase `classification` - the after-ledger-clean, before-modelo-prep helper.

## Outcome

`clasificar` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
