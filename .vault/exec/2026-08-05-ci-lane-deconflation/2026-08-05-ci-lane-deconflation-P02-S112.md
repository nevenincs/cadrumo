---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0c41d815357bb51eab18c9eb5b210376a2f612467798daef761cd0945f55bd09'
step_id: 'S112'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Close the historical printed-identity census through its final candidate filtering.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`
- `src/cadrumo/_data/registry/aeat/modelos/353`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S112.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s112-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: the exact row cleared Modelo 353 as the target-order parser artifact and classified Modelo 303 box 27 as a semantic-alias hazard, not an omission. The 18-model census then had one confirmed computed-but-short harmful case, Modelo 303 box 45. No fresh receipt is claimed.
- S113 and later filing-export measurement are downstream and not S112 evidence.
- This docs-only reconciliation changes no source, plan, baseline, threshold, or default index.
