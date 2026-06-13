---
step_id: S42
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S42 - IvaWalletReconciliationError registry and envelope tests

## Outcome

Extended `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
with three real-behavior tests covering the S41 raise migration.

## Tests added (3)

1. `test_iva_wallet_reconciliation_error_is_registered_in_error_registry` — asserts
   `"REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT" in ERROR_REGISTRY`
2. `test_iva_wallet_reconciliation_error_round_trips_through_build_error_envelope` —
   constructs the error, calls `build_error_envelope`, asserts code, retryable, suggestion
3. `test_negative_max_wallet_age_days_raises_iva_wallet_reconciliation_error` —
   calls `reconcile_iva_compensation_wallet` with `max_wallet_age_days=-1` using a
   real wallet observation; asserts `IvaWalletReconciliationError` is raised (not bare `ValueError`)

## Pytest outcome

15 passed (12 pre-existing + 3 new) in 21s. No mocks, no skips, no xfail.

## Commit SHA

`22f502b69`
