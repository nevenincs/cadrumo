---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:63f2b857ce8ca83fc482df72441ae6e792efdcd37600b4c859607e40f566a772'
step_id: 'S109'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Record the historical printed-identity census and its stated scope limit.

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro`
- `src/cadrumo/_data/registry/aeat/modelos/123`
- `src/cadrumo/_data/registry/aeat/modelos/714`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S109.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s109-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: the plan row's one printed-formula spelling matched modelos 303, 714, and 123. It recorded 123 as the correct control, 714 as manual-entry weakness rather than a wrong computed result, and 303 as the confirmed omission already owned through S108. No fresh source or test receipt is claimed.
- The three-model set was a floor, not a corpus census: prose and alternate printed-formula shapes were outside the search. S110 and later filtering are downstream and not S109 evidence.
- This docs-only reconciliation changes no source, plan, baseline, threshold, or default index.
