---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:d92d0478ae90ab5900f71b9d274a72693e069a102b4240e68857f184c1e7d8fe'
step_id: 'S32'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Drop the stale runner count from the load-sizing gate, leaving the invariant it actually asserts

## Scope

- `dev/ci/tests/test_machine_aware_load.py`

## Changes

M dev/ci/tests/test_machine_aware_load.py

## Notes

The gate opened by naming a runner count that three documents disagreed about. It
asserts that no lane uses an unbounded worker count, which holds at any number, so the
count is gone rather than corrected to a fourth value.
