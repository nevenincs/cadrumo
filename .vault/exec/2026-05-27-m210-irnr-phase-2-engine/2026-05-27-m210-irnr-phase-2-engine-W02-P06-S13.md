---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:64deb5231ae04ee4caeab15b38b3a6a020143cc00250013e2792ae25114be891'
step_id: 'S13'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# add the `source_jurisdiction` provenance pass-through on the M151 observation model

## Scope

- `src/aeat/application/aggregation`

## Description

- Reconcile the completed M151 observation provenance pass-through to this historical Step.
- Verify that `ImpatriadoIncomeObservation` retains the Spanish-source jurisdiction after classification.

## Outcome

Completed by commit `24c43acfe8` under the dedicated Modelo 151 source-scope plan. The observation model carries `source_jurisdiction`, and only an admitted Spanish-source row produces an observation. The later plan's execution record is the implementation authority; this record restores the missing traceability link for S13.

## Notes

No new production code was authored in this reconciliation Step.
