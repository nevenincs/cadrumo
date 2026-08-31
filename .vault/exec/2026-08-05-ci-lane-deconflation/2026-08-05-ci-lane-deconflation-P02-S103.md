---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9ef2257ee47863aca748e45a1289b50c7d0591ee919bd95a6bc80c797da6db73'
step_id: 'S103'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Record the historical independent corroboration of the already-owned Modelo 390 recargo omission and its measurement correction.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390`
- `src/cadrumo/_data/registry/aeat/modelos/303`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S103.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s103-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: the exact P02.S103 plan row independently corroborated the already-owned Modelo 390 recargo omission; it was not a new finding or a competing ownership claim. No fresh source, registry, or test receipt is reconstructed.
- The row records the essential correction to its first measurement: formula expressions are trees. A flat top-level read falsely suggested every recargo tier was absent; recursive traversal instead found the three nested tiers and aligned the result with the peer's legal-tier analysis. The six-casilla count included transitional rate variants and did not contradict the peer's four legal tiers.
- Lifecycle boundary: S104 and later work extend the historical measurement into separate Modelo 303 analysis. They are downstream and do not validate or replace S103's corroboration.
- This docs-only reconciliation changes no registry data, formula, source, plan state, baseline, threshold, or default index.
