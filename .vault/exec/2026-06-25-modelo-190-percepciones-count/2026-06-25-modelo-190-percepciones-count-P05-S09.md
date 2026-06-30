---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S09'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Add the pull equals calculate percepciones-count parity test

## Scope

- `src/aeat/application/calculations/tests`

## Description

- Verify the producer/store/resolver/bound-casilla path that backs pull equals calculate for the percepciones count.
- Run the focused M190 e2e tests.

## Outcome

- `test_persisted_withholding_set_is_readable_by_the_store` proves the producer writes the same typed withholding rows that the resolver reads.
- `test_m190_percepciones_count_resolves_distinct_from_store_to_bound_casilla` proves the encrypted store, `WithholdingSourceResolver`, binding value, and bound casilla projection produce the distinct count.
- `test_calculate_190_reconciles_111_quarters_for_two_adjacent_years` proves the annual M190 calculation uses the distinct withholding count while monetary totals continue to fold from M111 quarterly filings.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- The parity evidence is scoped to the current typed producer/store and calculate binding path. No separate external AEAT pull lane was available in this local test slice.
