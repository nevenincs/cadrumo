---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S03'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---




# `schema-hardening` `P01.S03`

Selected the Modelo 200 maintenance-employment correction family as the first
implementation candidate and blocked the remaining optional/numeric families
pending manual source lookup.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P01-S03.md`

## Description

The selected candidate is a compact 12-row grid where labels distinguish
`RDL 6/2010` from `RDL 13/2010` while sharing `DT 13a.2 LIS`. The audit records
that generic `con`/`sin` normalization is too broad and must not be treated as
a harmless axis globally.

## Tests

Validation was source-visible classification review only. No production code was
changed in this step.
