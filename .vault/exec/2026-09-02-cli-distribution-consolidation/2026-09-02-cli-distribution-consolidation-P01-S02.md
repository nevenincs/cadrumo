---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4b95b6d465a14b96bea2173a167e2fcfd8c4180f1b5abbfcce30b1d8751debaf'
step_id: 'S02'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Re-pin the three selected-path import contracts against a real cohort run

## Scope

- `dev/packaging/python_cohort.py`

## Changes

M .vault/research/2026-09-02-cli-distribution-consolidation-research.md

## Notes

No source change was required. The contracts landed in the preceding Step were
verified against the probe's own conditions - the three distributions built,
installed into an isolated site, and the probe run with `AEAT_INSTALL_SITE` and
`AEAT_DEPENDENCY_SITE` bound to it - and returned the same deltas with a zero exit
for all three paths. The Step's purpose was confirmation, and the values it would
have re-pinned were already correct.
