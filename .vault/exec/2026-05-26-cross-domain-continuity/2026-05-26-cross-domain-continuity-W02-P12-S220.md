---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S220'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-003 reject invalid period token at modelo work create time not at calculate time

## Scope

- `M202 currently accepts --period 1T at create then fails calculate with no-revision-for-period`
- `period validation must fire at create using the modelo revision's declared period catalogue`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Reconciled the Modelo 202 create-time period validation to its landed evidence.
- Confirmed `3675e3d57c` supplied the implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
