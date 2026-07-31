---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:85c40cc9da1c020eccaebbe10823b616a1062797a64db8982243127f262075e2'
step_id: 'S38'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# delete duplicate _MODELO_APPLICABILITY_RULES and derive_modelo_applicability from application copy

## Scope

- `replace with thin re-export from domain module`
- `src/aeat/application/overview/_applicability.py`

## Description

- Reconciled the canonical applicability-source collapse to the Wave-2 review.
- Confirmed `30065a92e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S39 through S42; each row receives its own record.
