---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a733b581ce6cd29d898e6fc64915ba4f3207fb6a159a4df0cc2f27b9d2a628f5'
step_id: 'S04'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Respecify the three Trusted Publisher bindings against the adopted workflow and environment

## Scope

- `RELEASING.md`

## Changes

M RELEASING.md

## Notes

The preceding Step in this Phase, publishing the primary name's reservation, is left
open: it is an irreversible write to an external index and needs credentials that are
not available to the executing agent. The binding specification landed here is what
makes that Step actionable for whoever holds them.
