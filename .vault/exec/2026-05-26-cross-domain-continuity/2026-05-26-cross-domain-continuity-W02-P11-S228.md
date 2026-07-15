---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S228'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-INES-2 CRITICAL fix profile-fact key-namespace divergence between persistence and calendar lookup

## Scope

- `third_party_transactions_above_347_threshold persists as obligations.third_party_transactions_above_347_threshold via config profile show but calendar reads it as unset and warns the key is not declared`
- `same defect class as W01.P05 boolean canonical drift but in a different namespace`
- `src/aeat/application/overview/__init__.py`

## Description

- Reconciled the profile-fact namespace correction to the Wave-2 evidence audit.
- Confirmed `13ab0f056d` supplied the landed correction.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The finding was originally critical and later corrected by the cited commit.
