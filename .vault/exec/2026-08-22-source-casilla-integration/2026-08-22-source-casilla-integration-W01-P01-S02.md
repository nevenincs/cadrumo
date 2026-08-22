---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:4dccd78a97221571092a1574ef8bfdb7d26569ece1a1657cde0e98f888e1256b'
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
- Replace ambient expiry validation with explicit caller-supplied expiry posture evaluation.
- Replace prose follow-up with a typed action identity, owner-inheritance, deadline, and completion contract.
- Close grounding locators over validated HTTPS, catalogue-reference, and repository-reference shapes.

## Outcome

`SourceConnectivityCensusRow` now wraps stable candidate identity with the S02
adjudication metadata. Every row requires typed re-fetchable grounding and
ownership. Blocked rows require a review condition, expiry, and a finite typed
follow-up; connection candidates require a review condition and follow-up;
manual-by-design rows require an explicit review condition. Expiry is evaluated
deterministically through `expiry_posture(as_of=...)`, and a follow-up with no
distinct owner explicitly inherits the row owner.

## Notes

Ruff and module compilation passed. Runtime contract checks admitted a complete
blocked row, refused malformed HTTPS locators, proved owner inheritance, and
proved fixed-date current/expired boundary behavior. The repository-wide clock
seam test no longer reports `source_connectivity.py`; it remains red on nine
unrelated concurrent user-profile bare-clock reads. Formal refusal tests remain
assigned to S05; this correction changed no test files and added no connected
proof fields.
