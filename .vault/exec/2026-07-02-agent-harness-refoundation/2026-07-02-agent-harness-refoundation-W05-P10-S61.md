---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:e7fde734352470b169be299983db7928e9f0cb7d6268d8e128bfdb47c0a10d9c'
step_id: 'S61'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-390 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-390/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-390` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `iva_regime` equals `GENERAL`/`SIMPLIFICADO` (annual summary of the quarterly Modelo 303; same filer set).

## Outcome

`preparar-modelo-390` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

None.
