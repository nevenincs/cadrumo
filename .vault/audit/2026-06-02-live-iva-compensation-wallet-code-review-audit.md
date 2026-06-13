---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-compensation-wallet-w06-p15-s56-session-reuse-live-read-exec]]'
---

# `live-iva-compensation-wallet` Code Review

## S56-SESSION-REUSE-AND-WALLET-QUERY-001 | MEDIUM | Per-declaration timeout could lose to outer surface timeout

Reviewed the uncommitted `W06.P15.S56` slice for AEAT no-write safety, active-profile Cl@ve session reuse, partial filed-history failure reporting, wallet entrypoint query preservation, privacy exposure, centralized external constants, and non-tautological focused tests.

The code-review subagent found that the per-declaration capture timeout reused the same setting as the outer filed-history surface timeout. That allowed the outer surface cancellation to win before the inner declaration wait could return a structured `FiledHistoryPartialFailure` report, especially after time already spent walking the declaration register.

Fixed by adding the central `aeat_live_iva_declaration_capture_timeout_ms` setting, validating that it is lower than `aeat_live_iva_surface_timeout_ms`, enrolling it in `env/.env.example`, and using it for individual Modelo 303 filed-declaration observation capture. Focused tests now prove the timeout hierarchy is enforced.

The wallet entrypoint change preserves query state only after the configured AEAT wallet host and path pass the existing read guard, and diagnostics continue to redact query values. The auth-session change scopes persisted session reads/writes/deletes to the active profile storage session instead of global storage.

Residual risk remains open and is product-significant: local tests and redacted diagnostics do not prove the live wallet/cartera surface works. A fresh operator-observed authenticated read-only run is still required before the feature can be called production-ready. No AEAT filing, payment, confirmation, amendment, represented-taxpayer submission, or tax-return filing path is accepted or permitted.
