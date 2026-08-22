---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:e4d2896347484798a4bbcee44737fd85b94f76b23899874c03a00e7dbc455045'
step_id: 'S02'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# define grounding, ownership, review-condition, expiry, and bounded-follow-up fields

## Scope

- `src/cadrumo/core/source_connectivity.py`

## Description

- Re-read the accepted S01 review and preserve the opaque candidate identity.
- Ground the row shape against existing immutable evidence and date contracts.
- Add typed, re-fetchable grounding locators and bounded explanatory text.
- Add the strict census row with disposition, owner, review condition, expiry, and bounded follow-up.
- Refuse blocked, candidate, and manual dispositions that omit their required actionability metadata.
- Keep connected-slice proof absent for the separately authorized S03 contract.

## Outcome

`SourceConnectivityCensusRow` now wraps stable candidate identity with the S02
adjudication metadata. Every row requires grounding and ownership. Blocked rows
require a review condition, future expiry, and bounded follow-up; connection
candidates require a review condition and follow-up; manual-by-design rows
require an explicit review condition.

## Notes

Ruff and module compilation passed. Runtime contract checks admitted a complete
blocked row and refused incomplete blocked and manual-by-design rows. Formal
refusal tests remain assigned to S05; this step changed no test files and added
no connected proof fields.
