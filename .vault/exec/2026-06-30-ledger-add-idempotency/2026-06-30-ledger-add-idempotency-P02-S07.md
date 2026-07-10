---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S07'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Wire manual rows into the existing day-key likely-duplicate advisory so a probable manual duplicate warns non-blockingly and never blocks a genuine movement

## Scope

- `src/aeat/application/ledger/_actions_import.py`

## Description

- Add a real-repository test proving a movement entered manually is recognised by a later import of the same movement (`imported=0`, `skipped=1`).

## Outcome

Landed in commit `3d8a6c14b`. No production change was needed in `_actions_import.py`: the import dedup already scans every catalogue row; the enabling change was the P02.S05 fingerprint stamp, which makes the manual row's identity canonical rather than fallback-derived.

## Notes
