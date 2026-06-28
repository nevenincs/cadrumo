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

After commit, a fresh Cl@ve Móvil auth retry was attempted with the 120 second operator window. It failed with typed `auth_completion_timeout` and diagnostic `20260602T174331Z`. The diagnostics showed the request route reached the Cl@ve Móvil request page with a verification code, but operator phone state remains unknown until the operator reports whether the app prompted and whether it was accepted. No read-only IVA capture ran after this failed auth attempt.

The operator later reported that the `20260602T174331Z` request did prompt but was missed. A subsequent auth attempt reached the AEAT representation gate and failed closed because the own-name selector shape was not recognized; the driver was hardened to accept either the centrally configured own-name label selector or own-name input selector, while still refusing representative/unknown representation choices. Focused auth and wallet representation-gate tests passed and the fix was committed. A post-fix fresh auth retry then failed with typed `auth_completion_timeout` and diagnostic `20260602T181937Z`; it reached the Cl@ve Móvil request page with a verification code, but no persisted session was saved and no IVA read surface ran.

A later fresh Cl@ve Móvil attempt succeeded and persisted a reusable non-expired session. The combined 2022-2026 read reused that session and authenticated successfully, but filed-history failed with the old fixed outer timeout while walking Modelo 303 around 2023 4T. A 2026-only read then succeeded for filed-history with zero captured rows, and a 2023-only read succeeded for filed-history with four captured Modelo 303 observations. This proves the declaration-query route is usable for those bounded year slices, but it also proved the fixed filed-history surface timeout was too small for multi-year capture. The backend now scales the filed-history surface timeout by requested year count.

Wallet/cartera remained failed in every authenticated retry. Even after query preservation and delayed execute-shell polling, AEAT still returned an executable `CarteraCuotas` shell with no wallet table after the guarded read-query action. The driver correctly failed closed and did not interpret that shell as an empty wallet or zero pending balance.

After fixing the CLI profile-key registration regression and applying the year-scaled filed-history timeout, the full 2022-2026 combined read was rerun with the persisted Cl@ve session. Auth succeeded with session reuse and filed-history succeeded with 12 Modelo 303 observations captured/calculation-promoted. Wallet/cartera still failed closed with the same executable `CarteraCuotas` shell and no wallet table. This is accepted live evidence for the declaration-query/filed-history path only; it is not accepted wallet/cartera evidence.

The local `iva-wallet history` reload surface then loaded the persisted profile-local state without contacting AEAT. It reported the same 12 filed-history rows and 8 carry-forward lots. Exact live amounts were not copied into this vault record. The reload also reported a nonzero unallocated applied amount and zero persisted authority decisions, so calculation/reconciliation follow-up remains open: filed-history-derived carry-forward state exists, but wallet authority is still missing and no final wallet-vs-history authority decision has been persisted.

## Notes

No AEAT write, filing, payment, confirmation, amendment, represented-taxpayer submission, or tax-return filing path was attempted. The wallet/cartera failure is now narrowed to a post-auth, read-only Pre303/cartera execution-shell problem: query stripping and delayed shell polling are fixed locally, but the live wallet route still does not yield parseable wallet evidence. The full-span filed-history route now works with year-scaled timeout and persists/reloads aggregate evidence shape; wallet/cartera remains the unresolved live blocker, and history-only reconciliation remains provisional until authority decisions are persisted.
