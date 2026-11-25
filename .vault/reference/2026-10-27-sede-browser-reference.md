---
tags:
  - '#reference'
  - '#sede-browser'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:c8554094a8ce442d6103a90bc3885ef65494604295d2cac15a27f3af9c679502'
related: []
---

# `sede-browser` reference: `in-app Sede browser grounding`

## Summary

Read-only discovery of the tree at `feature/tui` on 2026-10-27, for the in-app Sede browser. Each locator was re-read that day.

**Browser ownership and launch.**
- Provisioning installs full Chromium and chromium-headless-shell under `components/playwright` (`native/application/src/provisioning/browser.rs:919`); Python sets `PLAYWRIGHT_BROWSERS_PATH` (`src/cadrumo/adapters/outbound/aeat/browser/factory.py:459`). Playwright is 1.64.0 (`uv.lock`).
- `BrowserSession._launch_chromium` uses `launch_persistent_context` on a per-session temporary profile with `accept_downloads=False` and `headless` from settings (`src/cadrumo/adapters/outbound/aeat/browser/session.py:266-306`). Authenticated contexts are separate `new_context` calls carrying storage state and certificate provisioning (`session.py:341-381`).
- A live operation owns its browser through `own_provider_browser` (`src/cadrumo/application/live/live_operation_execution.py:61-71`), which registers the resource scope as `OperationOwnedResource.PROCESS`.

**Session custody and reuse.**
- Storage state is captured from the context, hashed into `storage_state_sha256` and saved encrypted with provider metadata (`src/cadrumo/adapters/outbound/aeat/auth/authenticator.py:690-721`). That capture refuses a session without certificate metadata, so Cl@ve providers capture through their own adapters.
- Guarded publication: `ensure_live_authenticated_session` stages writes with `session_store().defer_writes()` and publishes under the effect guard between `UNKNOWN` and `UPDATED` reports (`src/cadrumo/application/live/session.py:57-98`); `active_verified_session` applies `AeatAccessGate.require_live_read` first (`session.py:101-141`). `DeferredSessionWrites` is at `src/cadrumo/adapters/outbound/aeat/auth/session_store.py:51`.
- Acquisition runs through `ensure_authenticated_aeat_session` (`src/cadrumo/application/auth/sessions.py:338`) under `acquire_auth_acquisition_lock`, which never waits on a live lock (`src/cadrumo/application/auth/acquisition_lock.py:288`).
- Cl@ve Movil forces a headed browser for the QR branch unless non-QR is preferred (`src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:708-717`).

**Operation capabilities.**
- `build_live_operation_definition` fixes `interaction_kinds` empty and `OperationReconciliationPolicy.INTERRUPT` (`src/cadrumo/application/live/live_operation_registration.py:32-58`). Live capability sets declare cancellation `UNSUPPORTED` and deadline `ABSENT` (`src/cadrumo/application/operations/capabilities.py:330-350`).
- `OperationCancellation` offers `COOPERATIVE` and `CONTAINED`, `OperationDeadline` offers `COOPERATIVE` and `ENFORCED`, `OperationClosePolicy` offers `REQUEST_CANCEL` (`src/cadrumo/core/operations.py:115-137`).
- The supervisor leases for 10 minutes, bounds execution to one hour and cleanup to two minutes (`src/cadrumo/entrypoints/operation_composition.py:98-100`).

**Remote-state guard.**
- No context-wide route exists in the browser session; the only page-wide route is `src/cadrumo/adapters/outbound/aeat/sede/censal_navigation.py:70`. Step S02 of `2026-09-24-aeat-live-write-guard-plan` is open.
- Hosts: `[aeat.domains]` in `src/cadrumo/core/external_constants.toml:11-23`, with `sede` at `:13`; the Cl@ve IdP apex comes from `sanctioned_gov_idp_host_suffixes` (`src/cadrumo/core/remote_authority.py:112-132`).

**Transport.**
- Python frames: 64 KiB maximum, kinds `J`, `E` and `S` (`src/cadrumo_client/transport/frame_io.py:38-48`); the document reader refuses any other kind (`frame_io.py:100`).
- Rust frames: the same bound and kinds (`native/application/src/runtime_client.rs:40-48`), a 5 s per-frame budget (`:50`), 16 KiB transfer chunks with a 1 MiB transfer limit (`:51-52`), and a reader that refuses any kind but `J` and `E` (`:316`). A single read loop demultiplexes replies and pushed events (`:601-625`).
- The window relays registered operations through `native/application/src/person_operations.rs` (submit `:1672`, observe `:1651`, cancel `:1973`), with a 16 MiB assembled projection bound (`:67`); the Censo band's observe pattern is `native/desktop/src-tauri/src/shell/user_profile/censo.rs`.
- The profile worker opens a control channel and an operation channel, each verified against the native parent and boot id (`src/cadrumo_runtime/host/worker.py:84-145`).

**Window.**
- `AEAT_SEDE` is `native/desktop/frontend/src/shell/links.ts:7`; the palette action `link.aeat` is declared at `native/desktop/frontend/src/App.tsx:2093` and the rail's AEAT item calls it at `App.tsx:2854`.
- Host shell modules, including `external.rs`, `channel.rs` and `token.rs`, are under `native/desktop/src-tauri/src/shell/`. The register is `src/cadrumo_client/contracts/navigation.toml`; it has no Sede element today.
