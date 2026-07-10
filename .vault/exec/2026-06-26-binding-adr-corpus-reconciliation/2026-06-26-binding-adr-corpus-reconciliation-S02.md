---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S02'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# REWORK: re-point the calculation-aggregation-taxonomy Status from the apex to the phase ADRs (mechanism ownership kept

## Scope

- `value-layer dedup via phase 2.3)`
- `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`

## Description

- Reconstruct the execution record for the already-checked S02 row.
- Confirm commit `c2ff972dfd` re-pointed `2026-06-10-calculation-aggregation-taxonomy-adr.md`.
- Verify the status block now assigns value-layer deduplication to the phase ADRs.

## Outcome

- S02 is backed by landed evidence. The aggregation-taxonomy ADR remains accepted
  for mechanism ownership, while the duplicate relation and `previous_filing`
  value-layer implementation is explicitly assigned to future phase 2.3 rather
  than to a central apex.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence command: `git show --stat --oneline c2ff972dfd`.
