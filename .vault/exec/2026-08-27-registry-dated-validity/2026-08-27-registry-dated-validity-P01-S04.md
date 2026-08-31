---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f154c763341c79e04ba4ac76d1dca74261e480d499efc565ec9c46596e58e13c'
step_id: 'S04'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Rewrite the two year-coverage gates off the year-named-filename premise onto derived window coverage, replacing the withhold-a-file bite proof with a narrow-a-window bite proof, keeping both assertions on the property and never on a tally, and keeping the resolver-refuses-a-miss anchor

## Scope

- `src/cadrumo/application/registry/tests/ and src/cadrumo/domain/iva/tests/`

## Changes

- `M` `src/cadrumo/application/registry/tests/test_exact_key_corpus_year_coverage.py`
- `M` `src/cadrumo/domain/iva/tests/test_year_coverage_matches_supported_filing_years.py`
- `verify:` `pytest src/cadrumo/application/registry/tests/test_exact_key_corpus_year_coverage.py` -> `fail`
