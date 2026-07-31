---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:587e4d2d1331cf8415b61da9ea12f6a313bee7f0f6f6230f7188d34797594b4a'
step_id: 'S14'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# add the per-row segregation gate in the M151 classifier so a row with `source_jurisdiction != "ES"` produces a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation, anchored on LIRPF Art 93.5

## Scope

- `src/aeat/application/aggregation`

## Description

- Reconcile the completed M151 per-row Spanish-source segregation classifier to this historical Step.
- Verify that non-Spanish and unresolved jurisdictions become typed audit-visible issues rather than base observations.

## Outcome

Completed by commit `24c43acfe8` under the dedicated Modelo 151 source-scope plan. The classifier admits only `source_jurisdiction == "ES"` and emits `BECKHAM_FOREIGN_SOURCE_SEGREGATED` with the rejected code for a foreign row. The classifier-based shape is the architect-approved decision recorded by the source-jurisdiction closing review.

## Notes

No new production code was authored in this reconciliation Step.
