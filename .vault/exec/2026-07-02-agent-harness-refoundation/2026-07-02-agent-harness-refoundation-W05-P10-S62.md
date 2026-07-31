---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c095955819f14fcc4de5669076604d2af16c5c9e9a4bcb2dceb4d55513ece651'
step_id: 'S62'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the pyme-sociedad selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/pyme-sociedad/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `pyme-sociedad` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `entity_type` equals `legal_entity`.

## Outcome

`pyme-sociedad` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
