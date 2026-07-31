---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:67321339f6f5dd8e25e2471b2de623c41447bfea9e6c004100d31e57ffb2fa25'
step_id: 'S13'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: VERIFICATION GATE 1-AFTER - re-run the #1 M303 refunded-period, #7 M390 box 97, and #12 M390 box 662 regression gates after each carry-reconciliation sub-step and assert ZERO casilla value shifts against the recorded baseline

## Scope

- `src/aeat/application/modelo/tests/test_modelo_390_fifo_carried_pending.py`

## Description

- Verification gate 1 (after): re-run the #1 M303 refunded-period, #7 M390 box-97, and #12 M390 box-662 regression gates plus the pull-vs-calculate parity and cross-period clean-state surfaces after the carry-reconciliation edit, and assert ZERO casilla value shifts against the recorded baseline.

## Outcome

- After-gate green and byte-identical to the S10 baseline: 66 tests passed across the same surfaces. The full calculations, iva_compensation, filed-capture, and wallet-engine integration suites also passed (456 tests). No casilla value shifted from the back-door-injection removal.

## Notes

- The R2 carry-trust layer (`revision_carry_outcome`, the clean-state evidence gate) was confirmed untouched; the P03 change is purely the value-layer injection removal beneath the trust layer.
