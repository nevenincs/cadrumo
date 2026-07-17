---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add _ledger_validation_bad catch to ledger_split

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Reconciled the historical ledger validation work to the Wave-1 commit review.
- Confirmed `aff4a4c7e` covers the per-verb validation discriminator series.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-27 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S08 through S11; each row receives its own record.
