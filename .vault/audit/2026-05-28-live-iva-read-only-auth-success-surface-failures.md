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

Follow-up execution on 2026-05-28 found and fixed one local storage/session
regression before another read attempt: the combined backend capture now opens
the selected active profile's secure-storage session around auth preflight,
remote reads, and acquisition-manifest persistence. A full read-only retry then
reused the persisted Cl@ve session and again failed closed with filed-history
timeout plus wallet/cartera DOM-drift outcomes.

A privacy regression was also corrected: live auth preflight output now renders
the active profile as `<profile-id>` rather than the raw local bucket/profile
identifier.

Follow-up execution on 2026-05-28 also closed the observed Playwright
cancellation-noise defect. Combined live IVA remote-state capture now installs
a narrow event-loop exception filter while bounded browser read surfaces run.
The filter suppresses only Playwright `TargetClosedError` contexts caused by
surface timeout/cancellation and delegates unrelated loop exceptions. A focused
unit test proves both behaviours, and a read-only live smoke run with an
expired persisted Cl@ve session produced a typed operator-timeout result without
post-command `TargetClosedError` logging. This smoke run did not reach the
filed-history or wallet/cartera read surfaces, so it is not accepted as IVA
surface evidence.
