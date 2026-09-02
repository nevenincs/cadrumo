---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8eb525fcdc360a1b232b68be54f4ccf0ba70363a3ab62136e52fb2b6febe250f'
step_id: 'S29'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Rename the runners to the product-prefixed account convention

## Scope

- `.github/workflows/ci.yml`

## Changes

M .github/actionlint.yaml
M dev/ci/tests/test_runner_queue_watchdog.py

## Notes

Workflows select runners by label set, not by name, so the rename itself is an
operator action on the runner registrations and the fleet manifest rather than a change
here. Two in-repo surfaces named a runner and are corrected.

The label comment claimed the Scoop label keeps other Windows lanes off the publication
runner. Labels are additive and this fleet has one Windows runner, so the label selects
that runner for the Scoop lane and excludes nothing. Isolating the publication path
needs a second runner, not a second label.
