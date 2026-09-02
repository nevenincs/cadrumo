---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9fd4e07cbc5debe14d10907c5c2099a89b8d2e1e6012d63f3574ff7559b5fef0'
step_id: 'S09'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Restate the artifact-storage prohibition as a no-cross-run assertion

## Scope

- `dev/ci/tests/test_change_class_tiers.py`

## Changes

M dev/ci/tests/test_change_class_tiers.py

## Notes

The repository-wide prohibition was retired rather than narrowed to an allowed list.
Ten jobs across four workflows already relied on artifact storage to hand a built
cohort from the job producing it to the jobs proving it, and three of those lanes
survive this decision. An allowed list would have left the gate permanently red over
legitimate use. The invariant that holds is that no workflow reads an artifact from
another run, which is asserted directly and carries a defect proof.
