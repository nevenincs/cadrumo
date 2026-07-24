---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S21'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Define the per-mode checkpoint port protocol with the declared no-op arm and the frontend honesty surface (save-and-exit disabled with an explicit message when checkpointing is unavailable)

## Scope

- `src/cadrumo/application/flows/_checkpoint.py`

## Description

- Define the per-mode checkpoint port protocol with a declared no-op arm and the frontend honesty surface: save-and-exit is disabled with an explicit message when checkpointing is unavailable.
- Harden the no-op arm to fail fast rather than silently discard per review finding H2.
- Landed in `91a5d0cc28`; per-mode and no-op honesty hardened in `2b2c93bf90`.

## Outcome

The checkpoint port declares whether each mode can persist; unavailable modes surface an explicit disabled save-and-exit rather than a silent no-op, and the no-op arm fails fast.

## Notes

Review finding H2 required the no-op arm to be loud (fail-fast) instead of quietly discarding; the fix rode `2b2c93bf90`.
