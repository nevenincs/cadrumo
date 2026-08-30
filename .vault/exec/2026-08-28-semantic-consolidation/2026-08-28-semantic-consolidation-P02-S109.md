---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:de8897d976462225fa10e27fdf271a0d5bf7ace170ccf3c5260d7bb5eae0cb4b'
step_id: 'S109'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Collapse the confidence bound onto the canonical unit-proportion predicate at both the transaction validator and the CLI gate, which restated the same zero-to-one range a third and fourth time

## Scope

- `src/cadrumo/domain/transactions/model_validation.py`
- `src/cadrumo/entrypoints/cli/_review.py`

## Changes

- `M` `src/cadrumo/domain/transactions/model_validation.py`
- `M` `src/cadrumo/entrypoints/cli/_review.py`
- `verify:` `pytest src/cadrumo/domain/transactions -n 0 -m unit` -> `pass` (237)

## Notes

A triage sweep reported the CLI restating the transaction model's zero-to-one
bound. Confirming it found a third site: the model's own validator declared
`_CONFIDENCE_MIN` / `_CONFIDENCE_MAX` rather than reading the canonical
unit-proportion constants, so the same bound stood in three places, two of them
inside the supposedly-canonical side.

The CLI keeps its localised refusal and loses only the bound, which is the
shape `_decimal_parsing` already documents as correct: the grammar lives in
core, the instructive refusal is what the CLI legitimately owns.
