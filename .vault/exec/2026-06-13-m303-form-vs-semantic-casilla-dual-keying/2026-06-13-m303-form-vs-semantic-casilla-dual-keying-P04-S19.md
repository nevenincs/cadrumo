---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S19'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Add one box-equals-source consistency verification predicate per populated box using the new equality operator, each grounded in the box legal_refs, to catch a future mis-edit (box re-flipped to manual or projection pointed at the wrong source)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Add one box-equals-source BLOCKING_RULE consistency predicate per populated box (ten `equals` predicates) in `verification_expectations/0001-verification_predicates.toml`, each grounded in the box legal_refs (devengado art. 88, deducible art. 92).
- Catches a future mis-edit (a box re-flipped to manual or a projection pointed at the wrong source); a copy cannot drift within one evaluation.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
