---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S56'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-compensation-consultation-research]]'
---

# `live-iva-compensation-wallet` `W06.P15.S56`

## Scope

Live IVA read-only surface, active-profile storage readiness, and Cl@ve retry diagnostics.

## Description

- Ran vaultspec-rag code and vault searches for active-profile secure-storage drift and live IVA cartera consultation surfaces.
- Fixed secure-object deterministic object-key migration drift so repository construction no longer fails during profile creation.
- Fixed access-gate directory-mode authorization export drift so application imports no longer block profile creation.
- Fixed the IVA/invoices import cycle by making invoice validation error lookup lazy and exporting `InvoiceValidationError` from the invoice public surface.
- Created and selected a readable live IVA profile record using operator-provided env configuration without writing raw private identifiers into code, tests, or vault artifacts.
- Configured Cl@ve Móvil and verified profile/provider identity alignment through redacted CLI status output.
- Attempted a fresh Cl@ve Móvil login with the configured 120 second operator window.

## Outcome

Local backend blockers were fixed enough for the active profile to become readable and Cl@ve configuration to become aligned. The live authentication attempt failed with typed `auth_completion_timeout`; no authenticated AEAT read was completed and no live IVA wallet or filed-history value was extracted.

## Notes

The Cl@ve diagnostic requires the operator-observed phone state before it can be closed. No AEAT write, filing, payment, confirmation, amendment, or represented-taxpayer submission was attempted.
