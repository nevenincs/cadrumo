---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9603aca0460801258977a6f93f1151a2f074429dcc47d84f228ef99c25cec411'
step_id: 'S92'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Strengthen the no-revision refusal finding with an internal precedent that settles it, and record one smaller defect found beside it.

## Scope

- `src/cadrumo/domain/calculations/registry/temporal.py`
- `src/cadrumo/domain/calculations/registry/errors.py`
- `src/cadrumo/application/modelo/_binding_readiness.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S92.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s92-execution-self-review-audit.md`

## Notes

- Historical reconciliation only: the exact P02.S92 plan row establishes the adjacent selector precedent (`AmbiguousRevisionSelectionError.candidate_ids`) and the formerly silent `NoRevisionForPeriodError` branch in `_binding_readiness.py`. It contains no retained terminal receipt, so this record makes no fresh test or CLI-output claim.
- Lifecycle boundary: S90 identified the operator-facing accepted-set gap and S91 observed the corpus timing. S94 later added `available_revision_ids` at the selector's raise sites and logged the consumer exception; S95 later supplied focused verification. Current code remains consistent with those successors, but neither downstream implementation nor its receipt is S92 evidence.
- This docs-only reconciliation changes no source, plan state, baseline, threshold, or default index.
