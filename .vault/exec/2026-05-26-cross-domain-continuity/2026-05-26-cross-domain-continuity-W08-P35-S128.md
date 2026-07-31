---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:ecf61343ccf964427c17891a651d0fc0c5fb1ef709368cca0ce1aa6d9a0e1ee2'
step_id: 'S128'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# de-hardcode site 6 of 17

## Scope

- `src/aeat/application/modelo/_actions.py`

## Description

- Reconciled the operator-message localisation change to the grouped W08 execution evidence.
- Confirmed `b6991aeb1` supplied the reviewed batch.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The grouped execution record covers S123 through S139; each row receives its own record.
