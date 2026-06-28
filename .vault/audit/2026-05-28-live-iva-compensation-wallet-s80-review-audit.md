---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-compensation-wallet-W09-P22-S80]]'
---

# `live-iva-compensation-wallet` Code Review

S80-001 | INFO | No blocking findings
Reviewed the S80 cancellation-noise slice. The exception filter is scoped to
the combined live IVA remote-state capture and delegates unrelated event-loop
exceptions to the previous/default handler. The focused test exercises both the
suppressed real Playwright TargetClosed exception path and unrelated exception
delegation. No HIGH or CRITICAL findings were identified.

S80-002 | LOW | Surface evidence remains open
The live smoke run used an expired persisted Cl@ve session and produced a typed
operator-timeout result, so it proves the cancellation-noise path did not
regress CLI logging but does not prove filed-history or wallet/cartera surface
functionality. This remains covered by the open S56/S77 plan rows.

S80-003 | INFO | 2026-06-02 cancellation follow-up passes
Reviewed the follow-up change after a read-only live capture exposed
Playwright `net::ERR_ABORTED` frame-detach logging during command shutdown. The
implementation keeps the cancellation handler installed through the combined
capture command's event-loop teardown, extends suppression only to the observed
Playwright cancellation family, and centralizes the drain delay in `Settings`
plus `.env.example`. Focused ruff, live acquisition/taxonomy/config tests,
locale audit, and the short read-only live smoke passed.

S80-004 | LOW | Live extraction remains provisional
The 2026-06-02 live evidence still contains no accepted filed-history or
wallet/cartera data: the full read-only capture failed closed with filed-history
timeout and wallet/cartera DOM drift, and the short smoke intentionally used a
one-second surface timeout. S56/S77 must remain open until the actual AEAT read
surfaces return accepted redacted aggregate data.

S80-005 | LOW | Non-IVA registry warnings slated
The 2026-06-02 live capture emitted Modelo 347 quarter semantic-role warnings
during registry loading. They are not part of the IVA cancellation-noise fix and
are correctly tracked under the plan's non-IVA findings row for owner review.
