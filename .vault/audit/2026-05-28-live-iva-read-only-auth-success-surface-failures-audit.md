---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-auth-testimonial-correction-audit]]'
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

Follow-up execution on 2026-06-02 rechecked the same defect after the codebase
shifted toward a more centralized live backend. A full read-only capture
authenticated successfully and submitted no filing, payment, confirmation,
represented-taxpayer choice, or write action. The capture still did not obtain
accepted IVA data: filed-history timed out and wallet/cartera reported DOM
drift. During command shutdown it also exposed a second cancellation-only
Playwright report: `net::ERR_ABORTED` with a detached frame during navigation.

The cancellation filter now covers both observed Playwright cancellation
families, keeps the handler installed through the combined capture command's
event-loop teardown, and sources its drain delay from centralized settings.
Focused ruff/tests, locale audit, and a short read-only live smoke passed on
2026-06-02. The short smoke reused a persisted Cl@ve session and failed closed
with typed read-surface timeouts without post-command cancellation logging. It
is accepted only as auth/session/shutdown-hygiene evidence, not as evidence that
filed-history or wallet/cartera data extraction is functional.

During the 2026-06-02 live capture the registry loader emitted Modelo 347
quarter semantic-role warnings. Those warnings are non-IVA findings and remain
slated for owner review under the plan's non-IVA findings row; they were not
changed in this cancellation slice.

Follow-up execution on 2026-06-02 shifted from backend polishing to live-surface
diagnostics. The declarations-register driver now records redacted page-shape
context for navigation/form/search failures, and the combined IVA acquisition
report now carries redacted failure context through CLI output and persisted
acquisition manifests. Operator-facing text added in this slice uses
`adapters.sede.errors.modelo_unavailable` and was populated through
`aeat.locales` for `es`, `en`, `ca`, and `hu`.

Read-only live evidence:

- A one-year run for Modelo 303 / 2026 authenticated successfully, submitted no
  filing/payment/confirmation/represented-taxpayer data, and reached the
  declaration-query route. Filed-history succeeded with zero captured rows for
  that year. Wallet/cartera still failed closed with a surface timeout.
- A shorter read-only smoke proved the new diagnostics on both failed surfaces:
  filed-history timed out at progress `walk_declarations_register` for Modelo
  303 / 2026, and wallet/cartera timed out at
  `fetch_iva_compensation_wallet` for target 2026 / 1T.

No private taxpayer values, filed amounts, wallet balances, expediente ids, or
history rows are accepted into this audit. This is accepted as route and
diagnostic evidence only. It is not accepted as proof that live IVA wallet state
can be read, nor as proof that multi-year filed-history capture is complete.
