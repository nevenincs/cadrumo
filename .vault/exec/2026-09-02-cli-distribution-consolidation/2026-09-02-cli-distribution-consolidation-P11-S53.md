---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8d7f110d9c9be4a093910219514023636039c28d3dcee60cb2e814486b91eec7'
step_id: 'S53'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Close the workflow-reading gates that crash or drift against the live workflow set

## Scope

- `dev/ci/tests/test_self_hosted_fleet.py`

## Changes

- `A` `dev/ci/workflow_runner_targets.py`
- `M` `dev/ci/tests/test_self_hosted_fleet.py`
- `M` `dev/ci/tests/test_runner_queue_watchdog.py`
- `M` `dev/ci/tests/test_ci_workflow.py`
- `M` `dev/ci/tests/test_machine_aware_load.py`

## Notes

One failure remains in the suite and is left deliberately: the ledger scale benchmark's CPU budget. The breaching quarter moves between runs while the workload is strictly monotonic, and a fixed first-quarter workload varied 34% on the same tree, so the reading is host contention rather than a regression. The budget was not widened.

## Scope

- `dev/ci/tests/test_self_hosted_fleet.py`

## Changes
