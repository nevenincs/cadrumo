---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:1a3805252ba0c512f842be005a4ad03a0476315bcdb88f9135fa7b1d9c4a6f91'
step_id: 'S13'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Record every mismatch and candidate continuity decision as an explicit review disposition

## Scope

- `dev/registry/migration`

## Description

- Record all current equal-to-source values by locale and semantic source.
- Record the 64 Spanish Modelo values as official source text rather than translation debt.
- Record the 33 Hungarian M100 `Index` dispositions through the locale CLI allowlist.

## Outcome

Resolved by the 2026-08-05 identical-source adjudication research and
`src/cadrumo/locales/_intentional_identical.json`. The current inventory has
zero unresolved equality candidates: generic Catalan 30, generic Spanish 51,
Spanish Modelo source 64, and Hungarian 63, including 33 M100 `Index` keys.

## Notes

Spanish source values were preserved verbatim. No semantic claim was inferred
from English equality alone; continuity and wording conflicts remain bounded
manual review items.
