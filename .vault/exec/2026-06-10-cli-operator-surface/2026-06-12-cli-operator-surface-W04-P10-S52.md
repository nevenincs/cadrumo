---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S52'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P10.S52 IVA Wallet Correction Application Path

Scope: verify the guarded IVA wallet correction path.

## Description

- Ran application tests for IVA wallet correction.
- Verified correction requires an existing seed, records a reason, and refuses correction after filed consumption.

## Outcome

S52 is closed. The IVA wallet seed correction path is guarded and tested.

## Notes

- Checks run: `pytest src/aeat/application/modelo/tests/test_iva_wallet_correction.py`.
