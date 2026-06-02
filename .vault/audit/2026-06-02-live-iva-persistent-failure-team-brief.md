---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
  - '#team-brief'
date: '2026-06-02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures]]'
  - '[[2026-06-02-live-iva-surface-diagnostics-review]]'
---

# Live IVA Persistent Failure Team Brief

## Executive Summary

The persistent failure is not currently best described as "Cl@ve is broken" or
"the IVA live backend is wholly speculative." The accepted evidence splits the
system into two surfaces:

- Modelo 303 filed-history: now reaches the authenticated declaration-query
  route and has returned a successful zero-row 2026 result in a read-only live
  smoke.
- IVA wallet/cartera: still does not produce accepted read-only wallet evidence.
  It either fails closed as a live surface timeout, DOM drift, or an auth-gate
  redirect before we can prove a parseable wallet table or an executed empty
  wallet terminal shape.

Production readiness remains blocked by the wallet/cartera surface. The
dedicated team should treat filed-history as a partially working evidence input
and wallet/cartera as the primary unresolved live-read driver problem.

## Confirmed Causes

1. The direct wallet/cartera path is not yet proven to land on a parseable
   terminal page after authentication. The current driver navigates through
   Pre303 presentation, the Cl@ve selector route, an optional own-name
   representation gate, and an optional wallet execute-submit gate. Failures
   occur before the parser can accept a wallet table or a confirmed empty-wallet
   shape.

2. Historical diagnostics were too weak. Earlier runs collapsed materially
   different failures into timeout/DOM-drift symptoms without enough redacted
   phase context. The current slice improves this by carrying `failure_context`
   through application outcomes, persisted manifests, and CLI output, but the
   wallet-specific diagnostics still need a successful operator-observed run to
   pin the exact terminal shape.

3. Wallet/cartera direct-read failures are correctly fail-closed. The code must
   not infer a zero balance, empty wallet, or usable compensation value from a
   timeout, 403/auth-gate page, missing table, or unexpected form action.

4. The filed-history route and wallet route are legally and technically
   distinct. Official AEAT help says Modelo 303 declarations with result to pay
   or compensate may be absent from "Mis expedientes" and should be consulted
   through "Consultar declaraciones presentadas" or the Modelo 303 procedure
   query. That supports the filed-history route; it does not prove that the
   wallet/cartera running-balance route is equivalent or reachable by the same
   DOM sequence.

## Leading Hypotheses

H1. The wallet URL requires an app-local session minted by a specific Pre303
presentation flow, and the current route order is still wrong or incomplete.
The code attempts this, but the live terminal evidence is not yet sufficient.

H2. The wallet route is behind an AEAT auth/representation gate whose current
DOM differs from the configured selectors or expected own-name path.

H3. The wallet query is a read-only POST/submit action, but the current execute
gate detection is either firing too early, waiting for the wrong terminal
condition, or missing a post-submit redirect/frame update.

H4. AEAT exposes the running compensation balance primarily as a function of
filed Modelo 303 history and Pre303 state, not as a stable standalone table for
all taxpayers. This is plausible but not proven. The code must not implement
this as a legal conclusion until official guidance or live evidence supports
it.

## Code Surfaces To Assign

- `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
  - `fetch_iva_compensation_wallet`
  - `_open_authenticated_surface`
  - `_submit_wallet_execute_gate_if_present`
  - `_wallet_page_shape_context`
  - `is_aeat_wallet_auth_gate_redirect`
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
  - `_drive_search`
  - `_declarations_page_shape_context`
- `src/aeat/application/live/__init__.py`
  - `_capture_iva_remote_state_for_active_storage`
  - `_await_live_iva_surface`
  - `_redacted_failure_context`
- `src/aeat/entrypoints/cli/_app_live.py`
  - `_iva_remote_state_capture_lines`
  - `_compact_failure_context`

## Team Work Plan

1. Reproduce a read-only wallet/cartera run with operator-observed Cl@ve
   approval and archive only redacted structural diagnostics: phase, redacted
   landing URL, form/action paths, input ids/names/types, table counts, heading
   counts, raw HTML hash. Do not persist raw HTML or taxpayer values.

2. Add wallet-specific phase progress before each browser transition:
   Pre303 selector open, selector authorization, representation gate, wallet
   selector open, wallet execute gate inspection, execute submit, post-submit
   terminal wait, parser entry.

3. Split wallet failure modes more narrowly than generic timeout:
   pre303-auth-gate, pre303-representation-gate, wallet-auth-gate,
   wallet-form-action-drift, wallet-execute-missing, wallet-execute-stalled,
   wallet-table-missing, wallet-empty-terminal, parser-shape-drift.

4. Confirm whether the current `CarteraCuotas` URL is the intended official
   read surface for the authenticated profile, or whether the driver should
   discover the wallet link dynamically from the official Modelo 303/Pre303 page
   after authentication.

5. Keep the calculation engine blocked unless one of these is present:
   direct wallet/cartera evidence, filed-history-only evidence explicitly marked
   blocking, or an explicit taxpayer override. Never convert missing wallet
   evidence into zero.

## Acceptance Criteria

- A fresh operator-observed live run reaches either a parseable wallet table or
  a structurally proven empty-wallet terminal page without submitting any AEAT
  filing/payment/confirmation/represented-taxpayer data.
- The CLI and persisted manifest report the exact wallet phase and failure mode
  if the run fails.
- Filed-history success remains usable evidence but cannot mask wallet failure.
- No private taxpayer values, raw IDs, wallet balances, expediente ids, raw HTML,
  cookies, or support numbers are written to vault, tests, logs, or fixtures.

## Grounding Sources

- AEAT Modelo 303 help on why some filed Modelo 303 declarations do not appear
  in "Mis expedientes" and must be consulted through declaration-query routes:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-303/incidencia-consultar-303-expedientes-no-todas.html
- AEAT help for "Consulta de declaraciones presentadas", including Cl@ve access
  and model/year/period query behavior:
  https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html

