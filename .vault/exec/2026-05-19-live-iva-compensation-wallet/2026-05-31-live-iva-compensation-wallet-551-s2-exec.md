---
step_id: "S2"
tags:
  - "#exec"
  - "#live-iva-compensation-wallet"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
---

# live-iva-compensation-wallet #551 S2 — first_period_zero divergence variant

## What was done

Extended `IvaCompensationDivergence` in
`src/aeat/application/calculations/_iva_wallet_reconciliation.py` with the
`"first_period_zero"` literal and implemented detection in
`reconcile_iva_compensation_wallet`.

The function gained `is_first_iva_period: bool = False`. When `True`, two
non-blocking paths are added before the standard missing/stale branches:

- Fresh AEAT wallet with `total_pending == 0`: emits `first_period_zero`,
  `selected_authority="aeat_wallet"`, `blocked=False`.
- No wallet + seeded-zero local recurrence (`local_recurrence_amount == 0`):
  emits `first_period_zero`, `selected_authority="local_recurrence"`,
  `blocked=False`.

A stale wallet with zero amount is NOT promoted — it still routes through the
`wallet_stale` blocking branch. A non-zero wallet is NOT suppressed.

## Verification gate

`pytest src/aeat/application/calculations/test_iva_wallet_reconciliation.py
-k "first_period_zero or wallet_reconciliation"` — 19/19 passed.

## Tests added

4 new tests:

- `test_first_period_zero_with_aeat_wallet_zero_is_non_blocking`
- `test_first_period_zero_with_seeded_zero_local_record_is_non_blocking`
- `test_first_period_flag_does_not_suppress_non_zero_wallet_divergence`
- `test_first_period_flag_does_not_suppress_stale_wallet`

## Files touched

- `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
