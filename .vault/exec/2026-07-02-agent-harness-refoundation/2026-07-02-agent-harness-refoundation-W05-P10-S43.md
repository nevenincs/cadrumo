---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9020ba318fa4404f44d727dfe204e305d88a0e3ed520ceb1b32ffd7edb63b6c9'
step_id: 'S43'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Lift the intra-community-operator selection predicate from prose into the applies_when frontmatter field

## Scope

- `src/aeat/_data/agent/skills/intra-community-operator/SKILL.md`

## Description

- Add the structured `applies_when` frontmatter to the `intra-community-operator` skill, lifting its prose selection predicate into a machine-queryable form; the human `description` prose is preserved unchanged.
- Encoded predicate: profile_facts (any): `does_intracomunitario`, `iva.roi_enrolled`, `iva.oss_enrolled`, or `iva.intracommunity_operations_exceed_50000_eur` is true.

## Outcome

`intra-community-operator` now carries a validated `applies_when` predicate that the loader parses at skill load. The coverage gate `test_skill_applies_when.py` and the rule-surface drift gate stay green.

## Notes

The prose lists these as disjunctive triggers; encoded with profile_match `any` over the nested iva flags.
