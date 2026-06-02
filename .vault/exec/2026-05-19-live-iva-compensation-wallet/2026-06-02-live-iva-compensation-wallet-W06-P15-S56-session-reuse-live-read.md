---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
step_id: 'S56'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-compensation-consultation-research]]'
---

# `live-iva-compensation-wallet` `W06.P15.S56` session reuse live read

## Scope

Cl@ve session reuse repair and read-only IVA live-surface verification.

## Description

- Retried Cl@ve Móvil authentication with operator approval.
- Found that standalone `auth login` could report success while later read-only live capture reported no persisted session.
- Patched the operator auth service so local Cl@ve session reads, writes, and deletes run inside the selected active profile storage session.
- Retried live read-only IVA capture after confirming the local session probe reported a persisted, non-expired Cl@ve session.

## Outcome

Auth/session reuse is repaired for the observed path: the single-year read-only capture reused the persisted Cl@ve session and reached authenticated AEAT surfaces. Filed-history for 2026 completed with zero captured rows. Wallet/cartera still failed after the guarded wallet read-query action with `dom_drift`; no wallet balance was extracted.

The full 2022-2026 read-only capture reused the persisted session but failed filed-history with a live-surface timeout while processing 2024 Q1. A separate 2024-only retry failed by exceeding the outer command window without structured output. These are live product failures, not accepted evidence.

Follow-up implementation added a bounded per-declaration capture timeout for Modelo 303 filed-history observations. A partial filed-history capture is now reported as a failed surface with partial counts and redacted failed-declaration references instead of being reported as success or hanging the command. Focused local live-acquisition tests pass for this failure taxonomy.

A 2024-only live retry after the bounded-failure change returned structured output, but the persisted Cl@ve session had expired before filed-history capture could run. A fresh auth refresh then failed with typed `auth_completion_timeout` and diagnostic `20260602T171404Z`; operator phone-state classification remains required. No 2024 filed-history evidence was extracted in that retry.

Wallet/cartera investigation then found a concrete driver defect: the Pre303-discovered `CarteraCuotas` entrypoint validated the configured AEAT host and path but stripped query parameters before browser navigation. Because AEAT may carry read-only session/navigation state in the discovered query, this was a real live-surface regression candidate. The driver now preserves the validated query while continuing to drop fragments and redacting query values from diagnostics. Focused wallet parser, live acquisition, auth-session, and central settings tests pass locally. Live wallet/cartera extraction remains unproven until the next operator-observed authenticated read.

Code review found that the initial per-declaration timeout still reused the outer live IVA surface timeout, so outer cancellation could race and suppress the structured partial filed-history report. The fix added a central `aeat_live_iva_declaration_capture_timeout_ms` setting, validated it below the outer surface timeout, and wired filed-declaration observation capture to the shorter setting.

## Notes

No AEAT write, filing, payment, confirmation, amendment, represented-taxpayer submission, or tax-return filing path was attempted. The wallet/cartera failure is now narrowed to a post-auth, read-only Pre303/cartera navigation problem: query stripping is fixed locally, but the live route still needs a fresh authenticated verification. The filed-history failure is narrowed to a 2024 declaration-capture hang or timeout path; the backend now reports that failure as a structured partial filed-history failure instead of treating it as success or hanging indefinitely.
