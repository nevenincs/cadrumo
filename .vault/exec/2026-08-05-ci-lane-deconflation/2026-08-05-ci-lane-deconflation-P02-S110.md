---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:219058091655c079d4e34cb3f442f8e4630262462df67f4a775d8699d2cfffd8'
step_id: 'S110'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Record the historical printed-identity census and its extractor corrections without promoting it to a defect verdict.

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro`
- `src/cadrumo/_data/registry/aeat/modelos/322`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S110.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s110-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: S110 widened the printed-identity extractor from three to 18 modelos and corrected target-order pairing after impossible self-reference exposed a parser bug. Its ten clean models and candidates in 303, 322, and 353 are an inventory, not a defect verdict; box-id reachability can over-report semantic aliases. No fresh receipt is claimed.
- S109 is the predecessor limited search; S111 and later leaf-set filtering are downstream and own candidate adjudication.
- This docs-only reconciliation changes no source, plan, baseline, threshold, or default index.
