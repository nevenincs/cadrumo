---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:411a2db6f2ff3f800bce3ed35d341e5f56226ad09a099c89805cfadd475b2072'
step_id: 'S168'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in repair_integrity.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/repair_integrity.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S168.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s168-execution-self-review-audit.md`

## Notes

- This is a stale-plan reconciliation and makes no source change. `src/cadrumo/application/repair_integrity.py` is clean at 991 raw physical lines; `measure_module_lines()` reports that it is not a live size-budget-limit subject. No source provenance commit or refactor is claimed.
- Root ran `uv run --no-sync pytest -q src/cadrumo/application/tests/test_repair_integrity.py` with `13 passed in 6.83s`; collect-only found 13 tests in 0.19s. These are root-reported receipts retained as supplied evidence.
- No baseline, threshold, `--write-baseline`, `--accept-growth`, default-index, source, or plan mutation occurred.
