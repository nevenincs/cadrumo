---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S14'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Add an equality/consistency operator to the verification predicate DSL registry KNOWN_VERIFICATION_PREDICATE_OPERATORS, separately grounded, so a box-equals-source consistency predicate can be authored

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Add the `equals` operator to KNOWN_VERIFICATION_PREDICATE_OPERATORS in `src/aeat/domain/calculations/registry/_schema.py`, separately grounded with a docstring naming the M303 projection-consistency use.
- equals(["lhs_id", "rhs_id"]) — the two named casillas must hold the same value.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
