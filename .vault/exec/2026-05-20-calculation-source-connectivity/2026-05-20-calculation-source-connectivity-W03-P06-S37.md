---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:b4d31561216bb4c7558de412d44a7af39e35b8b42393a40d4d7790d89a90cb40'
step_id: 'S37'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# [RETIRED] Test non regional category profiles preserve existing Renta results

## Reconciliation outcome

Retired on 2026-07-17 with the dormant regional layer. Real registry-backed
state-law deductibility tests remain; only the synthetic regional comparison
was removed. The material below is historical execution evidence, not current
architecture.

## Scope

- `src/aeat/application/aggregation/test_renta_ledger.py`

## Description

Add `test_non_regional_category_profile_preserves_result_across_region`, running the aggregation over a non-override category once with `residence_ccaa=None` and once with a declared comunidad, and assert the observations and casilla values are identical.

## Outcome

Proves the region axis is inert for state-law categories while the override layer is empty. Landed in commit `1ca532e93a`. The existing renta aggregation suite is also byte-identical (24 passed). Gates green.

## Notes

Implements the S37 invariant of ADR `2026-07-04-renta-region-deductibility`: non-regional profiles preserve existing Renta results.
