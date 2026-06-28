---
step_id: S41
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S41 - introduce IvaWalletReconciliationError

## Outcome

Introduced `IvaWalletReconciliationError(CoreError)` in
`src/aeat/application/calculations/_errors.py`. Replaced the bare `ValueError`
in `_is_wallet_stale` (the only non-pydantic-validator raise site) with
`IvaWalletReconciliationError`. The three raises at lines 120/122/124 of
`_validate_selected_amount` are inside a `@model_validator` and were left
unchanged per step instructions.

## Files touched

- `src/aeat/application/calculations/_errors.py` — appended `IvaWalletReconciliationError(CoreError)`
- `src/aeat/application/calculations/_iva_wallet_reconciliation.py` — import `IvaWalletReconciliationError`; 1 raise migrated (line 568, `_is_wallet_stale`)
- `src/aeat/core/errors/registry/_application.py` — `REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT` entry
- `src/aeat/locales/{en,es,ca,hu}.yml` — `errors.refused.refused_iva_wallet_reconciliation_invariant` key (via `python -m aeat.locales set`)

## Raises migrated (1 site)

1. `_is_wallet_stale` — "max_wallet_age_days must be non-negative"

## Commit SHA

`22f502b69`
