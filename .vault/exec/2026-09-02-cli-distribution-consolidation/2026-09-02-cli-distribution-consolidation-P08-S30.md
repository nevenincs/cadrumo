---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4ce86848d67d9cc32ce0357587dbd0c1db178e236c89fc86af64d29b6d84b241'
step_id: 'S30'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Delete the branch-only runner probe workflows

## Scope

- `.github/workflows/ci-runner-probe.yml`

## Changes

D .github/workflows/ci-runner-probe.yml
D .github/workflows/ci-runner-probe-final.yml
D .github/workflows/ci-runner-probe-matrix.yml
M dev/ci/tests/test_runner_queue_watchdog.py

## Notes

Deleting them exposed a gate that had been passing on them: the watchdog gate required
the shared module to be invoked by script path, and only the probes did that. Every
shipping lane invokes it as a module, so the gate had never actually constrained them.
It now names the form the lanes use.
