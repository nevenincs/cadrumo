---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S56'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the preparar-modelo-309 selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/preparar-modelo-309/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `preparar-modelo-309` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts: `iva_regime` equals `RECARGO_EQUIVALENCIA`/`EXENTO`/`REAGP`/`NO_APLICA`.

## Outcome

`preparar-modelo-309` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

Encodes the prose's 'no periodic IVA obligation at all' clause. The other clause - a one-off non-periodic trigger for an otherwise-periodic filer - is an event, not a stable profile fact, so it is not expressible in the profile-fact axis; documented here as the narrowest defensible predicate.
