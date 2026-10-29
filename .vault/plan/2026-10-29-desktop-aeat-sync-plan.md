---
tags:
  - '#plan'
  - '#desktop-aeat-sync'
date: '2026-10-29'
tier: L2
related:
  - '[[2026-10-29-desktop-aeat-sync-adr]]'
  - '[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-10-27-sede-browser-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-08-08-synced-history-consumption-adr]]'
  - '[[2026-10-03-aeat-live-write-guard-adr]]'
modified: '2026-10-29'
body_schema: body-v2
body_hash: 'sha256:52267106f6c17b5d495138bb064e2e714f74086e25ffa5c2a3d31eccb876eeaa'
---

# `desktop-aeat-sync` plan

Build the desktop window's AEAT sync page: area overview, browser and sign-in preflight, a host-run area queue with stop, distinct outcomes, and results.

## Description

Approved 2026-10-29

Authorization basis: the owner wrote "approved" in the conversation on 2026-10-29, covering this plan, the governing ADR and its three amendment proposals, after ruling the open questions: all four Python changes accepted; stop takes effect after the current step; per-area staleness 7, 30 and 90 days; census reachable from the global command palette, the profile page, the Modelo page and the AEAT sync page.

Decision coverage: `2026-10-29-desktop-aeat-sync-adr` (accepted) governs every Phase: the backend read `live.sync.status`, the four contract changes to existing live operations, the host command list and run model, outcome mapping and the page. Its three amendments are part of the accepted records `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr`, `2026-10-04-desktop-shell-adr` and `2026-08-08-sync-control-surface-adr` (P01.S01). Accepted records that constrain the work unchanged: `2026-10-27-sede-browser-adr` (P04 notification action, sign-in through the Sede view), `2026-10-24-rust-component-provisioning-adr` and `2026-10-18-dependency-provisioning-unified-setup-adr` (P03 and P04 browser preflight), `2026-10-04-application-sign-in-adr` (person session and reply bounds), `2026-08-08-synced-history-consumption-adr` (results stay evidence) and `2026-10-03-aeat-live-write-guard-adr` (reads only).

Scope: P01 decision; P02 backend read and contract changes; P03 host commands, run model and host tests; P04 frontend page, overview, flow and results; P05 locales; P06 Playwright scenarios; P07 review and the attended live check with the owner, last. Census review reuses the existing `profile_censo_*` host session and `ProfileSync` band; nothing about it is duplicated. It is reachable from a global command palette action, the profile page, the Modelo page and the AEAT sync census area (P04.S22, P04.S23, P06.S24).

Owner rulings of 2026-10-29, recorded in the governing ADR: all four backend changes are in scope; stop takes effect after the current step, with no cooperative cancel; staleness defaults are notifications 7 days, IVA wallet 30 days, census, filed declarations and identity checks 90 days (P02.S03, P02.S26, P06.S25); outcome classification is host-side through one closed table; notifications open the Sede browser at its start page; Borrador 100 is PDF import only and excluded from "everything".

## Steps

### Phase `P01` - Decision

Accept the governing ADR and apply its three amendments to the accepted records.

- [x] `P01.S01` - obtain the owner's acceptance of the governing ADR (open questions ruled 2026-10-29), then apply the three amendment proposals to their accepted records and retire the proposals; `.vault/adr/2026-10-29-desktop-aeat-sync-adr.md and the three amended accepted records`.
- [x] `P01.S02` - confirm by Haiku sweep the two implementation hypotheses (census review awaiting while other captures run; filed-discover yields bulk year and form pairs) and record any correction in the ADR; `src/cadrumo/application/user_profile/censal_operation.py, src/cadrumo/application/live/filed_history_discovery.py`.

### Phase `P02` - Backend status read and contract changes

Serve per-area AEAT sync state from the backend and remove paths, tax numbers and message parsing from the window's inputs.

- [x] `P02.S03` - extend the AEAT sync reader with IVA wallet, Borrador 100 and identity-check sources and backend-owned per-area staleness, keeping workbench.generation on the same reader; `src/cadrumo/application/aeat_sync/workspace_reader.py, src/cadrumo/application/aeat_sync/workspace.py`.
- [x] `P02.S04` - register the live.sync.status read operation with its request, result and refusal contracts, composing only the stores it needs and resolving the profile tax number in the worker; `src/cadrumo/application/aeat_sync/status_operation.py (new), src/cadrumo/application/live/live_operation_registration.py`.
- [x] `P02.S05` - make output_root optional on live.filed-capture.bulk, live.filed-history.pull and live.iva-wallet.history-capture with the worker defaulting to the settings directory, and remove the CLI client-side default; `src/cadrumo/application/live/ (three operation modules), src/cadrumo/entrypoints/cli/app_live_commands.py, src/cadrumo/entrypoints/cli/app_live_iva_commands.py`.
- [x] `P02.S06` - make nif optional on live.verify.nif-iva and live.verify.tgvi defaulting to the profile taxpayer number, and add a distinct typed refusal detail for an ended AEAT session in live captures; `src/cadrumo/application/live/verify_capture_operation.py, src/cadrumo/application/live/errors.py`.
- [x] `P02.S26` - test the per-area staleness defaults (notifications 7 days, IVA wallet 30 days, census, filed declarations and identity checks 90 days) at and across each boundary through the real reader; `src/cadrumo/application/aeat_sync/tests/`.
- [x] `P02.S07` - regenerate the contract manifest and run focused tests plus import, style, format and type gates; `src/cadrumo/_data/operations/contract_manifest.json`.

### Phase `P03` - Host commands and run model

Give the host named aeat_sync commands and a profile-held area queue with stop, resume and a closed outcome table.

- [x] `P03.S08` - add the aeat_sync host module with the closed admitted definition list, the named commands and their registration, checked by test against the manifest; `native/desktop/src-tauri/src/shell/aeat_sync/mod.rs (new), native/desktop/src-tauri/src/app.rs`.
- [x] `P03.S09` - implement the profile-held run: area order, per-year filed items, census session reuse, stop between items, reattach, discard on sign-out and profile change, settle waits that never become unknown; `native/desktop/src-tauri/src/shell/aeat_sync/run.rs (new), native/desktop/src-tauri/src/shell/user_profile.rs`.
- [x] `P03.S10` - implement the closed outcome table, session-ended pause and resume from the first item not brought, person-initiated retry, preflight from setup rows, sign-in through auth.session.acquire, and observation-event progress; `native/desktop/src-tauri/src/shell/aeat_sync/outcome.rs (new), native/desktop/src-tauri/src/shell/relay.rs`.
- [x] `P03.S11` - cover the run model and outcome table in desktop-host-unit-test, including unknown never retried and no id, code or path in any reply to the window; `native/desktop/src-tauri/src/shell/aeat_sync/tests.rs (new)`.

### Phase `P04` - Frontend page

Build the aeat-sync window view: overview, preflight, sign-in, selection, progress and results.

- [x] `P04.S12` - add the aeat-sync window view, host port and scenario host data, and route live operations to it; `native/desktop/frontend/src/shell/navigation/windowViews.ts, native/desktop/frontend/src/shell/aeatSync.ts (new), native/desktop/frontend/src/shell/tauriHost.ts, native/desktop/frontend/src/dev/scenarios.ts`.
- [x] `P04.S13` - build the six-area overview showing served states, dates and counts only; `native/desktop/frontend/src/components/aeatSync/AeatSyncPage.tsx (new)`.
- [x] `P04.S14` - build the flow: browser preflight with inline setup and automatic resume, sign-in choices including the Sede view, and area selection with years, forms and dry run; `native/desktop/frontend/src/components/aeatSync/ (new)`.
- [x] `P04.S15` - build live per-area progress with stop and the four outcomes, with explicit retry for failed and warned retry for unknown; `native/desktop/frontend/src/components/aeatSync/ (new)`.
- [x] `P04.S16` - build results: the shared census review band, filed declaration matches, notifications with read state, legal-receipt warning and open-in-Sede action, and Borrador import; `native/desktop/frontend/src/components/aeatSync/ (new), native/desktop/frontend/src/components/profile/ProfileSync.tsx`.
- [x] `P04.S22` - add a global command palette action, available on every page, that opens the one existing census flow (useCensoSync and ProfileSync over the profile_censo_* commands) without duplicating it; `native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/shell/profileCenso.ts, native/desktop/frontend/src/components/profile/ProfileSync.tsx`.
- [x] `P04.S23` - add a census entry on the Modelo page that opens the same census flow, and route the AEAT sync page's census area to it; `native/desktop/frontend/src/components/modelo/declarations/DeclarationsPage.tsx, native/desktop/frontend/src/components/aeatSync/`.

### Phase `P05` - Locales

Author every window string for the page through dev.locales in en, es, ca and hu.

- [ ] `P05.S17` - declare the page keys and author en, es, ca and hu catalogue entries through dev.locales in the informal singular, then regenerate the desktop strings; `dev/locales/desktop_interface_keys.py, src/cadrumo/locales/ (en, es, ca, hu)`.

### Phase `P06` - Playwright scenarios

Cover every page state with scenario-host data.

- [ ] `P06.S18` - add scenarios for browser missing then installed, signed out then signed in, and session expires mid-sync; `native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts (new), native/desktop/frontend/src/dev/aeatSyncFixture.ts (new)`.
- [ ] `P06.S19` - add scenarios for partial failure, unknown outcome, nothing found, dry run and stop; `native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts`.
- [ ] `P06.S24` - add scenarios proving the palette action, the profile page, the Modelo page and the AEAT sync census area all open the one census flow and reattach to a running census session; `native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts, native/desktop/frontend/tests/scenarios/user-profile.spec.ts`.
- [ ] `P06.S25` - add scenarios for each area showing possibly out of date at its served horizon (notifications 7 days, IVA wallet 30 days, others 90 days) from scenario-host data; `native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts, native/desktop/frontend/src/dev/aeatSyncFixture.ts`.

### Phase `P07` - Review and live check

Review the integrated work and confirm it with the owner on a real AEAT session.

- [ ] `P07.S20` - review the integrated backend, host and page against the governing ADRs and append findings to the feature audit; `.vault/audit/ (feature audit scaffolded by the owning verb)`.
- [ ] `P07.S21` - run the attended live check with the owner on a real AEAT session: preflight, sign-in, everything, stop, results and census review; `native/desktop/ (installed dev build, no installer)`.

## Parallelization

Agent roles: Haiku (Explore) for every read-only sweep, inventory and evidence lookup; Sonnet at high effort for bounded coding Steps; Opus at medium effort for integration, cross-layer Steps and review.

- P01 is sequential and owner-gated; nothing else starts before the ADRs are accepted.
- P02 (Sonnet high, one worker per Step; S05 and S06 may run in parallel with S03 and S04 because they touch different operation modules; S26 follows S03; S07 regenerates the manifest once, after S03 to S06 and S26) and the host skeleton P03.S08 (Sonnet high) may proceed in parallel once P01 closes; P03.S09 onward needs the regenerated manifest from P02.S07.
- P04 page shell and overview (S12, S13) may start against the scenario host while P03 runs; P04.S14 to S16 need the host command shapes from P03.S08. P04.S22 (palette action) may run in parallel with S12 to S16 because it touches only the shell palette and the existing census port; S23 follows S16.
- P05 locales (Sonnet high) run after P04 wording stabilizes; one writer owns `dev/locales` and the catalogues.
- P06 scenarios (Sonnet high) follow P04 and P05; P03.S10 (outcome table, resume and sign-in across host, relay and setup engine) is Opus medium.
- P07 review is Opus medium; the live check is attended by the owner and runs last.
- Write ownership is disjoint per Step; manifest regeneration, locale generation and commits are serialized. Haiku readers never edit.

## Verification

- `live.sync.status` returns each area's state for never brought, current, possibly stale and unavailable fixtures through the real reader, and costs a bounded read without `workbench.generation`.
- The four contract changes pass their operation tests and the CLI keeps identical behaviour with its client default removed; the contract manifest is regenerated and the closed host id list test passes against it.
- `desktop-host-unit-test` covers the run model: order, reattach, navigation survival, stop between items, session-ended pause and resume from the first item not brought, unknown never retried, and the outcome table for every admitted operation.
- Playwright scenarios pass for: browser missing then installed; signed out then signed in; session expires mid-sync; partial failure; unknown outcome; nothing found; dry run; stop; each area's possibly-out-of-date horizon; and the palette, profile page, Modelo page and AEAT sync census area all opening the one census flow.
- Staleness boundaries (7, 30 and 90 days) are tested through the real reader.
- Locale keys exist with real translations in en, es, ca and hu through `dev.locales`; no internal id, code or path appears in any window string or scenario snapshot.
- `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types` pass for touched Python; frontend type check and lint pass.
- The final review passes and the owner confirms the attended live check.
