---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S37'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the alta-contribuyente selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/alta-contribuyente/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `alta-contribuyente` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: workflow_phase `onboarding` - the pre-ledger onboarding helper, keyed to the start-of-engagement lifecycle point rather than a profile fact.

## Outcome

`alta-contribuyente` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
