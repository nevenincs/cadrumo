---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S17'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Narrow the devengado implies_any_nonzero advisory predicate to drop the now-populated constituents (03/06/09/11/13) and retire or retain it only for boxes that remain manual, so the advisory and calculate diagnostic stop firing for populated boxes and keep firing for manual ones

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Retire the devengado implies_any_nonzero advisory predicate: ALL its constituents (03/06/09/11/13) are now computed projections, so the predicate is satisfied by construction.
- Removed it rather than leaving a dead always-green predicate (no manual cuota box remains in the devengado constituent list).

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
