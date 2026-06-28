---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures-audit]]'
  - '[[2026-06-02-live-iva-surface-diagnostics-review-audit]]'
---

# Live IVA Persistent Failure Team Brief

## Failure Statement

The implementation has failed the required product outcome.

The required outcome is a read-only live AEAT consultation for the authenticated
declarante that can programmatically pull the AEAT-maintained IVA compensation
state needed to ground local Modelo 303 calculations. It must not file, amend,
confirm, pay, select a represented third party, or otherwise mutate AEAT state.

The current code does not yet deliver that outcome. It has only demonstrated
that one Modelo 303 declaration-query route can be reached after authentication
for a one-year query that returned zero rows. That is route evidence, not a
working IVA compensation-state read. It does not prove multiyear filing-history
pull, submitted-declaration download, Pre303 state extraction, wallet/cartera
state extraction, or calculation reconciliation against AEAT's binding state.

## Current Failure Split

- Declaration-query consultation: required and not optional. This is one of the
  intended live consultation surfaces for pulling filed Modelo 303 information
  for the declarante without filing anything. The current implementation has
  reached the route once, but has not proven complete multiyear extraction or
  current compensation-state reconstruction from AEAT records.
- IVA wallet/cartera or Pre303 compensation state: required authority input if
  AEAT exposes the running balance there. The current implementation has not
  produced accepted read-only wallet/Pre303 compensation evidence. It fails
  closed as timeout, DOM drift, or auth-gate/route uncertainty before proving a
  parseable wallet table, a Pre303 compensation field set, or a legally grounded
  empty/absent state.

Until one of those live consultation paths yields the binding compensation state
or a legally grounded derivation from AEAT-filed records, the live IVA feature is
not functional.

## Confirmed Causes

1. The product-level read is missing. The code does not yet consult AEAT live
   surfaces end-to-end and extract the declarante's binding IVA compensation
   state. A successful route visit is not enough.

2. The direct wallet/cartera path is not yet proven to land on a parseable
   terminal page after authentication. The current driver navigates through
   Pre303 presentation, the Cl@ve selector route, an optional own-name
   representation gate, and an optional wallet execute-submit gate. Failures
   occur before the parser can accept a wallet table or a confirmed empty-wallet
   shape.

3. Historical diagnostics were too weak. Earlier runs collapsed materially
   different failures into timeout/DOM-drift symptoms without enough redacted
   phase context. The current slice improves this by carrying `failure_context`
   through application outcomes, persisted manifests, and CLI output, but the
   wallet-specific diagnostics still need a successful operator-observed run to
   pin the exact terminal shape.

4. Wallet/cartera direct-read failures are correctly fail-closed. The code must
   not infer a zero balance, empty wallet, or usable compensation value from a
   timeout, 403/auth-gate page, missing table, or unexpected form action.

5. The declaration-query route is a core required surface, not a fallback
   curiosity. Official AEAT help says Modelo 303 declarations with result to pay
   or compensate may be absent from "Mis expedientes" and should be consulted
   through "Consultar declaraciones presentadas" or the Modelo 303 procedure
   query. Therefore the dedicated team must implement robust read-only
   declaration-query extraction for the declarante. What remains unproven is
   whether current running compensation state can be read directly from
   wallet/Pre303, or must be reconstructed from AEAT-filed declarations and then
   explicitly labelled as such.

## Leading Hypotheses

H1. The wallet URL requires an app-local session minted by a specific Pre303
presentation flow, and the current route order is still wrong or incomplete.
The code attempts this, but the live terminal evidence is not yet sufficient.

H2. The wallet route is behind an AEAT auth/representation gate whose current
DOM differs from the configured selectors or expected own-name path.

H3. The wallet query is a read-only POST/submit action, but the current execute
gate detection is either firing too early, waiting for the wrong terminal
condition, or missing a post-submit redirect/frame update.

H4. AEAT exposes the running compensation balance primarily through filed
Modelo 303 declarations and Pre303 consultation state, not as a stable
standalone table for all taxpayers. This is plausible but not proven. The code
must not implement this as a legal conclusion until official guidance or live
evidence supports it.

H5. The current "wallet" naming may be too narrow. The required feature is not a
specific table name; it is the read-only AEAT consultation pipeline for the
declarante's binding IVA compensation state. The team should discover and
implement the actual official surface, even if the final route is declaration
query plus submitted-file extraction rather than `CarteraCuotas`.

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

1. Treat this as a failing live-read feature, not a nearly complete feature.
   The team objective is to make AEAT read-only consultation produce the IVA
   compensation state for the declarante or prove, with official/live evidence,
   exactly why it cannot be obtained from a specific surface.

2. Reproduce a read-only wallet/cartera run with operator-observed Cl@ve
   approval and archive only redacted structural diagnostics: phase, redacted
   landing URL, form/action paths, input ids/names/types, table counts, heading
   counts, raw HTML hash. Do not persist raw HTML or taxpayer values.

3. Add wallet-specific phase progress before each browser transition:
   Pre303 selector open, selector authorization, representation gate, wallet
   selector open, wallet execute gate inspection, execute submit, post-submit
   terminal wait, parser entry.

4. Split wallet failure modes more narrowly than generic timeout:
   pre303-auth-gate, pre303-representation-gate, wallet-auth-gate,
   wallet-form-action-drift, wallet-execute-missing, wallet-execute-stalled,
   wallet-table-missing, wallet-empty-terminal, parser-shape-drift.

5. Implement declaration-query extraction as a first-class live consultation
   path: multiyear Modelo 303 search, submitted declaration/file download where
   available, extraction of compensation-relevant fields, and persistence of
   redacted evidence references. This must be read-only and authenticated for
   the declarante.

6. Confirm whether the current `CarteraCuotas` URL is the intended official
   read surface for the authenticated profile, or whether the driver should
   discover the wallet link dynamically from the official Modelo 303/Pre303 page
   after authentication.

7. Keep the calculation engine blocked unless one of these is present:
   direct wallet/cartera evidence, filed-history-only evidence explicitly marked
   blocking, or an explicit taxpayer override. Never convert missing wallet
   evidence into zero.

## Acceptance Criteria

- A fresh operator-observed live run pulls the declarante's compensation-relevant
  AEAT state through declaration-query/submitted-file extraction, wallet/Pre303
  extraction, or both. A route visit without extracted state is not accepted.
- If wallet/Pre303 is the chosen direct source, the run must reach either a
  parseable wallet/Pre303 compensation state or a structurally proven
  empty/absent terminal page without submitting any AEAT
  filing/payment/confirmation/represented-taxpayer data.
- The CLI and persisted manifest report the exact wallet phase and failure mode
  if the run fails.
- Filed-history success remains usable evidence but cannot mask missing current
  compensation-state extraction.
- No private taxpayer values, raw IDs, wallet balances, expediente ids, raw HTML,
  cookies, or support numbers are written to vault, tests, logs, or fixtures.

## Grounding Sources

- AEAT Modelo 303 help on why some filed Modelo 303 declarations do not appear
  in "Mis expedientes" and must be consulted through declaration-query routes:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-303/incidencia-consultar-303-expedientes-no-todas.html
- AEAT help for "Consulta de declaraciones presentadas", including Cl@ve access
  and model/year/period query behavior:
  https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html
