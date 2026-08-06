---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:9d19506b12a4e06229e48942a07adc6ca44da4eff3c20376be04da752394ddb9'
step_id: 'S42'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# regression test asserting _MODELO_APPLICABILITY_RULES is a unique source with one definition and one identity

## Scope

- `src/aeat/domain/calculations/registry/test_applicability_canonical.py`

## Description

- Reconciled the canonical applicability-source collapse to the Wave-2 review.
- Confirmed `30065a92e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S38 through S41; each row receives its own record.
