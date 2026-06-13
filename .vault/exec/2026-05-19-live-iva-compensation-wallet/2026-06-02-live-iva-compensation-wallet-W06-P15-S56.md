---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S56'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures-audit]]'
---

# `live-iva-compensation-wallet` `W06.P15.S56`

Partial follow-up for the opt-in read-only live IVA evidence path.

## Description

- Add redacted page-shape diagnostics to the AEAT declarations-register driver
  for listing navigation, final-url drift, form render, modelo option, and
  Buscar click failures.
- Carry live IVA surface timeout progress into `LiveIvaSurfaceTimeoutError`,
  acquisition report outcomes, persisted acquisition manifests, and CLI output.
- Add wallet/cartera timeout progress so failures identify
  `fetch_iva_compensation_wallet` instead of only a generic wallet timeout.
- Add the missing `adapters.sede.errors.modelo_unavailable` locale key through
  `aeat.locales` for `es`, `en`, `ca`, and `hu`.

## Outcome

Focused tests and live smoke runs improved the diagnostic evidence path without
claiming production readiness. A read-only one-year live run reached the
authenticated Modelo 303 / 2026 declaration-query route and returned zero filed
rows. Wallet/cartera still failed closed. S56 remains open.

## Notes

No AEAT filing, payment, confirmation, represented-taxpayer selection, or other
write action was submitted. No private taxpayer values, filed amounts, wallet
balances, or expediente ids are recorded in this step record.
