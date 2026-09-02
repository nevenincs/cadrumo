---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c9745f4846bc63e851644faa017164ac8848c1022d40eb01930785847ba06f54'
step_id: 'S25'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Derive the required evidence rows from the whole inventory

## Scope

- `dev/release/readiness.py`

## Changes

M dev/release/readiness.py

## Notes

Rows are the union over every listed channel. A channel that cannot be proven leaves
the inventory rather than sitting in it unproven, so there is no longer a state where a
declared channel blocks nothing.
