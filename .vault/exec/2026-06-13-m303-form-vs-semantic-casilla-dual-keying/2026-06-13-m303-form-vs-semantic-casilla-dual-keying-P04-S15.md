---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S15'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Extend the predicate authoring-time validator to accept the new equality operator and reject malformed equality expressions

## Scope

- `src/aeat/domain/calculations/registry/_validate_surfaces.py`

## Description

- Extend the predicate authoring-time validator in `src/aeat/domain/calculations/registry/_validate_surfaces.py` to accept `equals` and reject malformed arity (a `_EQUALS_PREDICATE` regex + `_equals_predicate_arity_failures` helper).
- A non-binary or malformed equals expression fails registry load instead of silently holding at evaluation time.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
