---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:ebfcfea17ab5d45cb0025bdee2dcf6a6c529cbaa9bc0475002453cddaffecfb6'
step_id: 'S15'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add --reaffirm flag on ledger classify bypassing the no-op guard for explicit re-application

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Reconciled the historical explicit re-affirmation command to the Wave-1 commit review.
- Confirmed `dc38dcc43` supplied the reviewed CLI work.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
