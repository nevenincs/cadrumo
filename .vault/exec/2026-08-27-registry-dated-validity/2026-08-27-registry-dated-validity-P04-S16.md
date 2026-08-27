---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:2d0651faf670c91cb81b7bbd36fc2912b0ae7e8b5d118f4298bab72bdce2b4cc'
step_id: 'S16'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Prove every new gate bites by mutating the shipped corpus from outside the tracked tree, covering a stripped provision id, a window widened past its provision, a cap edited away from the AEAT figure and a cap schedule moved off a year the citations still cover, then re-run both coverage gates

## Scope

- `src/cadrumo/domain/categories/ and src/cadrumo/application/registry/tests/`

## Changes

- `verify:` `out-of-tree mutation of the shipped categories corpus, 5 proofs` -> `pass`
- `verify:` `pytest test_exact_key_corpus_year_coverage.py test_year_coverage_matches_supported_filing_years.py` -> `pass`

## Notes

Two of the five proofs were wrong on their first run and were corrected before
the recorded pass. One narrowed a cap row into an INVERTED span, so it reddened
the span validator and proved nothing about coverage. The other inverted its own
success condition and reported a correctly-dropped year as a failure; the
implementation was right and the proof was not. Both are recorded because a
bite proof that passes for the wrong reason is the failure this discipline exists
to catch.
