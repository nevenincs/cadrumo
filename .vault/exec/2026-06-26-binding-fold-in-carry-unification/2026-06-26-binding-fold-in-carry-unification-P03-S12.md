---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:ee33e8edb82da58b1897cbb92c98380c5abacc7c2f70640fec6140c491e17420'
step_id: 'S12'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-high-executor: reconcile the derive_303_compensation_available carry path onto the one wallet authority so the M390 box 97/662 FIFO partition derives from the one projection (apply-cached on collision)

## Scope

- `src/aeat/domain/iva_compensation/_carry_forward.py`

## Description

- Reconcile the `derive_303_compensation_available` carry path and the M390 box-97/662 FIFO partition onto the one wallet authority, so the M390 partition derives from the one projection.

## Outcome

- No code change required: analysis confirmed `derive_303_compensation_available` and `derive_iva_compensation_year_end_carry_partition` are shared carry arithmetic that already feed/defer to the wallet. `derive_303` computes the disponible casilla value stored on a filed observation, which the IVA-compensation-history projection reads to reconstruct the local recurrence the wallet reconciliation consumes; the M390 partition is consumed by the box-97/662 binding path (preserved via the P01 typed relation op). Neither is a parallel route to the wallet-owned compensación binding, so neither was changed.

## Notes

- Changing these pure carry computations would have been unnecessary churn on the highest-risk layer. The C3 fragmentation was the single back-door observation injection removed in S11; once removed, the wallet is the single authority and these paths already feed it. The M390 FIFO box-97/662 identity is preserved exactly.
