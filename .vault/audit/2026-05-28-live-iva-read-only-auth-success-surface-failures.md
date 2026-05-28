---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-auth-testimonial-correction]]'
---

# `live-iva-compensation-wallet` Live Read Attempt

Fresh Cl@ve Móvil authentication succeeded in an operator-observed run on
2026-05-28. The subsequent combined read-only IVA remote-state command reused
that authenticated session and submitted no AEAT filing, payment, confirmation,
represented-taxpayer choice, or write action.

The read-only acquisition did not obtain accepted IVA data. It returned typed
failures for both read surfaces:

- filed-history: `live_navigation_failed` via `LiveIvaSurfaceTimeoutError`;
- wallet/cartera: `dom_drift` via `SedeNavigationError`.

No private taxpayer values, filed amounts, wallet balances, expediente ids, or
history rows are accepted from this run. The only accepted evidence is the
redacted aggregate shape: authentication succeeded, both intended read surfaces
failed closed, and the combined command now returns typed failures instead of
hanging silently.

Follow-up remains open: the filed-history surface needs navigation diagnostics
for the timeout path, and the wallet/cartera surface needs DOM-drift analysis
against the authenticated AEAT page shape before live IVA grounding can be
called functional.
