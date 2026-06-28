---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S84'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# Divergence Ladder Engine Coverage

Scope: `src/aeat/application/calculations`, `src/aeat/application/modelo`.

## Description

- Add production Modelo 303 engine coverage for `wallet_lower`.
- Add production Modelo 303 engine coverage for `wallet_stale`.
- Add production Modelo 303 engine coverage for missing wallet and missing local recurrence.
- Reuse the Sede wallet parser-backed observation helper for stale-wallet evidence instead of constructing a separate test double.
- Assert blocked decisions refuse calculation before a `CalculationRevision` is persisted.

## Outcome

`S84` is complete. Non-private coverage now spans match, wallet-only, wallet-higher, wallet-lower, wallet-stale, missing, filed-history-only, and override paths across pure reconciliation plus the Modelo 303 calculation boundary.

## Notes

No live AEAT contact was made. No private taxpayer values were used. Export-layout and local-file workflow harness work remains tracked separately.
