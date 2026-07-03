---
tags:
  - '#exec'
  - '#modelo-190-percepciones-count'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S05'
related:
  - "[[2026-06-25-modelo-190-percepciones-count-plan]]"
---

# Enroll the withholding-count source in merge_source_resolutions and the owned-source set

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Inspect the live source mesh enrollment and resolver behavior.
- Run the withholding resolver, source-boundary, and focused M190 tests.

## Outcome

- `WithholdingSourceResolver` is enrolled in the live bucket source mesh in `src/aeat/application/modelo/_calculation_actions.py`.
- `test_resolver_materialises_distinct_percepcion_count` proves the enrolled resolver reads the encrypted withholding store and materialises the distinct percepciones count.
- `test_resolver_materialises_zero_with_advisory_on_empty_store` proves an empty withholding store materialises explicit zero with a non-blocking `source_issue`, not a silent blank or hard refusal.
- `test_s27_withholding_source_kind_is_enrolled_not_deferred` proves `withholding` is not treated as an unhandled deferred source for M190.
- Verification passed in the combined M190 slice: 22 passed.

## Notes

- No production change was needed for S05; the source is already enrolled.
