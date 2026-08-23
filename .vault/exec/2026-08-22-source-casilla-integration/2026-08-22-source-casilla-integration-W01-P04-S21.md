---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f28b62517128f9b3fb8cb99ccb104fa26fba31671cb1163be54a3bf657283b8e'
step_id: 'S21'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# classify assets and fincas with separate evidence, grain, and substitutability questions

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Classify the general encrypted asset register separately from asset amortization.
- Classify finca annual aggregates separately from both asset repositories.
- Record distinct source independence, grain, substitutability, revision, and destination questions.
- Attach owned finite official-source follow-ups and review expiry to both grounding blocks.

## Outcome

Assets and fincas are independently visible `grounding_blocked` candidates. Neither lexical proximity nor shared amortization vocabulary can collapse their source grains or authorize a Modelo 100 mapping.

## Notes

The strict bundled loader passed. Both rows are current as of 2026-08-23, expire on 2026-12-31, and require bounded adjudication by 2026-11-30.
