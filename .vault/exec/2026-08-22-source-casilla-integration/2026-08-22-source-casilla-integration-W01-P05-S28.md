---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d13d51d062210f3af9e202702ce68ca36fade8978cfdd51179ff2b880885c2f0'
step_id: 'S28'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# prove each ratchet failure mode bites under an external mutation

## Scope

- `dev/source_connectivity/tests/test_check.py`

## Description

- Mutate the live discovered capability set with one unclassified addition.
- Remove one explicitly reviewed capability from live discovery.
- Expire a blocked row at the deterministic civil-date boundary.
- Remove the bounded follow-up from an unresolved candidate.
- Promote a candidate to connected without live connected proof.

## Outcome

Every ratchet failure mode independently bites under an external mutation: additive drift, unexplained
disappearance, expired deferral, unactioned unresolved state, and unsupported connection. The suite uses
the real bundled census and the live independently discovered capability inventory.

## Notes

Ruff passed and all five mutation tests passed sequentially.
