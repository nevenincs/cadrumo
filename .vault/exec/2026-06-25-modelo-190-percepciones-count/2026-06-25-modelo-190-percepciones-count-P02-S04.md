---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S04'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Add grounded distinct-count tests where recurring quarters count once and two claves count twice

## Scope

- `src/aeat/domain/calculations/registry/tests`

## Description

- Inspect the distinct-count regression tests.
- Run the focused M190/withholding proof set.

## Outcome

- `test_percepcion_count_counts_two_claves_for_one_perceptor_twice` proves one NIF under two claves yields two percepciones.
- `test_percepcion_count_counts_recurring_perceptor_clave_once` proves recurring rows with the same `(perceptor, clave)` count once.
- `test_percepcion_count_subclave_distinguishes_percepciones` proves subclave is part of the distinct key.
- `test_percepcion_count_exceeds_distinct_perceptor_count` proves two perceptores with one under two claves yield three percepciones, not two perceptores.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- These tests assert against the fixture's clave-bearing row identity, not against the retired registry relation formula.
