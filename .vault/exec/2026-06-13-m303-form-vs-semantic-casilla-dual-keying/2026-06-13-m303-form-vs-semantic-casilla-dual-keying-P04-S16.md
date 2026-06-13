---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S16'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Implement the equality-operator branch in the predicate evaluator so the consistency predicate returns True iff the box value equals its semantic source value

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Implement the `equals` branch in the predicate evaluator `_evaluate_predicate_expression` in `src/aeat/application/modelo/_verification_actions.py` (real evaluator: holds iff lhs == rhs; missing reads as Decimal(0); defensive on malformed arity).
- Add the `_PREDICATE_EQUALS` regex and re-export it from `_actions.py` so the operator-parity gate test can reach it.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
