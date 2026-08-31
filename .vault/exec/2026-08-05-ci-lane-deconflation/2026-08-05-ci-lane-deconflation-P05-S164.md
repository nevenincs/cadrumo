---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:a7f9087c5bdaf33c4aff2e6af073d0bdbed4a3a58b3563792691d7b100e3f792'
step_id: 'S164'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in supervisor.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/operations/supervisor.py`

## Changes

- `M` `src/cadrumo/application/operations/supervisor.py`
- `A` `src/cadrumo/application/operations/supervisor_context.py`
- `M` `src/cadrumo/application/operations/tests/test_executor_contract.py`
- `M` `src/cadrumo/application/operations/tests/test_restart_reconciliation.py`
- `M` `src/cadrumo/application/operations/tests/test_supervisor.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S164.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s164-execution-self-review-audit.md`
- `verify:` `git show --check 359baf225823ae7c32aa7cab3c535e6b34c3f1c2` -> `pass`

## Notes

- Source provenance is `359baf225823ae7c32aa7cab3c535e6b34c3f1c2`, whose exact five-path source manifest is the modified supervisor, added private context sibling, and the three modified direct test consumers above. `supervisor.py` shrank from 1361 to 1241 raw physical lines after the restored property documentation; `supervisor_context.py` is 136 lines. Both are below the 1250-line default ceiling. No plan, baseline, threshold, or default-index mutation is present.
- The extracted `_SupervisorExecutorContext` remains private in the direct sibling. The three affected tests import it directly from `supervisor_context`; no compatibility facade or re-export was introduced.
- Source static checks are qualified executor and root-review evidence, not newly reproduced command transcripts in this record. The focused three-test selector ran zero tests and produced a runner-level nothing-ran outcome. It is not a pass and supplies no execution receipt.
- No baseline, threshold, `--write-baseline`, or `--accept-growth` action was taken.
