---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:93f30970a5b8ef2a7b4ec736d70d6ae966b2eedf4f2458ccbfadf2d15111c66b'
step_id: 'S01'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# Apply the source-year delta through the canonical relation coordinate resolver

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py`

## Description

Replaced the test-local period-only offset derivation with
`validate_relation_source_coordinate_coverage`, the production registry validator
that applies the offset year delta and resolves the resulting coordinate against
the source revision set. Historical previous-filing carries use the production
`_relation_is_prior_year_filing_carry` classification, preserving the accepted
pre-modelled-history boundary.

## Outcome

The owning module passes two tests. Ruff and BasedPyright are clean, and
`git diff --check` reports no defect. No selector mirror, tolerance, fake, mock,
patch, skip, or compatibility path was added.

## Notes

S01 and S02 are one load-bearing change in one test module: applying the year
delta and selecting the owning member of a split revision set cannot be
implemented or verified separately without recreating the retired mirror.
