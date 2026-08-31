---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d7aca3571e82ab5f0691aae21f9a731d1081e990d2980d2573b807547324c1b3'
step_id: 'S210'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in models.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/invoices/models.py`

## Changes

- `M` `src/cadrumo/domain/invoices/models.py`
- `A` `src/cadrumo/domain/invoices/normalization.py`
- `M` `src/cadrumo/domain/invoices/tests/test_models.py`
- `M` `src/cadrumo/domain/invoices/tests/test_counterparty_country_is_required.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S210.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s210-execution-self-review-audit.md`

## Notes

- Source commit `5849fee0a762f589aa5fc449dbe6ed604c9812df` reduced `models.py` from 1,411 to 1,109 raw physical lines and added direct sibling `normalization.py` at 340 lines.
- The private normalization/validation pipeline now has its canonical home in `normalization.py`. `models.py` uses only a module alias, avoiding a facade or re-export; public `derive_invoice_id` remains canonical in `models.py`, with explicit dependency injection avoiding a cycle.
- AST review reported all 24 definitions conserved. Independent source review reported C/H/M/L 0.
- The executor reported focused invoices pytest 66 passed in 19.26s and clean Ruff, formatting, and diff checks. Literal command transcripts are not retained, so these are qualified executor reports, not fresh receipts.
