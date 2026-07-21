---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S07'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Re-point M190 decl.total-percepciones to the count binding

## Scope

- `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes`

## Description

- Inspect the M190 registry casilla and binding records.
- Run the M190 percepciones e2e and round-trip tests.

## Outcome

- `decl.total-percepciones` points at binding `modelo-190-percepciones-anual`.
- `modelo-190-percepciones-anual` declares `source = "withholding"`, selector `fact = "percepcion_count"`, and aggregation op `count_distinct`.
- `test_m190_percepciones_count_resolves_distinct_from_store_to_bound_casilla` proves the resolver's binding value maps onto `decl.total-percepciones`.
- `test_modelo_190_sums_monetary_relations_and_binds_percepcion_count` proves the registry receiver composes the bound percepciones count with the remaining monetary relations.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- No registry edit was needed for S07.
