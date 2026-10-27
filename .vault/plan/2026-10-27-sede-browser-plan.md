---
tags:
  - '#plan'
  - '#sede-browser'
date: '2026-10-27'
tier: L2
related:
  - '[[2026-10-27-sede-browser-adr]]'
  - '[[2026-10-03-aeat-live-write-guard-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-06-04-live-auth-decomposition-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:561e1974c2cd384575a39a8d8a2ef960851c9101ffd791321ac1476f034a036b'
---

# `sede-browser` plan

## Description

Approved 2026-10-27. Basis: the user's choice, in the orchestrating session of 2026-10-27, of "stream our Chromium's page into a panel" followed by "implement 1)", together with the defaults recorded in `2026-10-27-sede-browser-adr` for the clarifying question the user left unanswered (browse and log in only, off-AEAT links in the system browser, session sharing through the same custody). Allowing full human use of the Sede, including submission and signing, is an open follow-up outside this plan and needs the user's approval.

The plan builds the in-app AEAT Sede browser: a Browser rail item, the AEAT rail item opening it at the Sede with an "Open in external browser" context menu, and a panel that draws the profile worker's own Chromium page streamed as JPEG images and forwards bounded CDP input. The panel and every CLI and TUI sync share one encrypted storage-state custody: the view seeds from it, logins in the panel publish to it, and the view republishes on close only after provider verification and a digest precondition.

Decision coverage: `2026-10-27-sede-browser-adr` (accepted) governs every Step. Its amendments of 2026-10-27 in `2026-10-03-aeat-live-write-guard-adr` govern P02.S04 and P05.S12 (operator-view policy, first fail-closed installation of the ruling 4 module on the view context). The amendment in `2026-10-04-application-sign-in-adr` governs P01 (view stream lane, attach token, unbinding on session retirement). The amendment in `2026-10-04-desktop-shell-adr` governs P03 and P04. `2026-06-04-live-auth-decomposition-adr` governs P02.S05 and P05.S12 unchanged: application auth owns acquisition and publication, the browser adapter owns context construction, and a running context is never re-seeded. `2026-07-21-desktop-capture-harness-adr` is out of scope and unchanged. S02 of `2026-09-24-aeat-live-write-guard-plan` remains that plan's Step; P02.S04 lands the module it names and installs it only on the view context.

## Steps

### Phase `P01` - view stream protocol and transport

Deliver the view stream lane on both legs: the B frame kind and control documents, the runtime host relay with attach binding, and the Rust client lane.

- [x] `P01.S01` - add the B frame kind confined to a view-connection codec, the 16-byte chunk header, the image assembler with latest-wins and violation refusal, the closed view.* control document models and shared test vectors, while every existing document reader keeps refusing B; `src/cadrumo_client/transport/frame_io.py, new src/cadrumo_client/transport/view_stream.py, new src/cadrumo_client/contracts/view_stream.py, new src/cadrumo_client/contracts/tests/view_stream_vectors.json, src/cadrumo_client/transport/tests`.
- [ ] `P01.S02` - add the runtime host view relay: the worker view channel endpoint beside control and operation channels, the person-connection attach request with a single-use 10 s attach token, view connection admission on the same native peer, two-image credit relay, and immediate unbinding on operation end, session retirement, connection close or violation; `src/cadrumo_runtime/host/worker.py, new src/cadrumo_runtime/host/view_stream_relay.py, src/cadrumo_runtime/host/profile_connection_operations.py, src/cadrumo_runtime/host/profile_connections.py, src/cadrumo_runtime/host/session_events.py, src/cadrumo_runtime/host/tests`.
- [ ] `P01.S03` - add the Rust view stream client: attach on the person connection, a dedicated verified view connection, B header validation against the shared vectors, image assembly, credit and upstream control writers, and zeroized buffers; `native/application/src/runtime_client.rs, new native/application/src/view_stream.rs, native/application/src/lib.rs`.

### Phase `P02` - Sede view operation

Deliver the live.sede.view operation in the profile worker: the context-wide guard with the operator-view policy, session seed and close-time publication through the canonical custody path, screencast and bounded input.

- [ ] `P02.S04` - add the public request-guard composition module of the live-write guard ruling 4 and the operator-view policy, and create the view context with the route installed before any page, service workers blocked, WebSockets closed, and refusal, popup, download and file-chooser notices through a page-observer hook; `new src/cadrumo/adapters/outbound/aeat/browser/request_guard.py, src/cadrumo/adapters/outbound/aeat/browser/session.py, src/cadrumo/domain/calculations/registry/remote_state_guard.py, src/cadrumo/core/remote_authority.py, browser and registry tests`.
- [ ] `P02.S05` - add the view session seed and close-time publication in application auth: resume or acquire through ensure_authenticated_aeat_session, provider capture and verification with identity alignment, the storage_state_sha256 precondition, deferred writes under the acquisition lock and effect guard, and the typed published, unchanged, kept-newer, verification-failed and unknown outcomes; `src/cadrumo/application/auth/sessions.py, src/cadrumo/application/live/session.py, src/cadrumo/adapters/outbound/aeat/auth/authenticator.py, src/cadrumo/adapters/outbound/aeat/auth/session_store.py, auth and live tests`.
- [ ] `P02.S06` - add the screencast and input adapter: a CDP session on the view page with Page.startScreencast JPEG sized and capped, immediate frame ack with newest-only retention, closed input variants translated to Input.dispatchMouseEvent, dispatchKeyEvent and insertText with clamping and rate bounds, navigation verbs and page dialogs, with no script evaluation; `new src/cadrumo/adapters/outbound/aeat/browser/screencast.py, new src/cadrumo/adapters/outbound/aeat/browser/view_input.py, src/cadrumo/adapters/outbound/aeat/browser/tests`.
- [ ] `P02.S07` - register live.sede.view with its own capability set (cooperative cancel, request-cancel close, no replay, process-owned, one view per profile), desktop human-only admission excluded from MCP projection, the acquire, browse and closing phases, idle and absolute bounds, and the worker view channel wiring, then regenerate the operation contract manifest; `new src/cadrumo/application/live/sede_view_operation.py, src/cadrumo/application/operations/capabilities.py, src/cadrumo/application/live/live_operation_registration.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo_mcp operation projection, generated operation contract manifest`.

### Phase `P03` - desktop host

Deliver the closed token-checked host commands, the view connection relay onto one Tauri channel, external-browser offers and cancellation on close or session loss.

- [ ] `P03.S08` - add the closed token-checked sede_view host commands (open, close, input, navigate, resize, credit, dialog, open offer externally), relay the view connection onto one top-document Tauri channel, hold offer URLs in the host with open_external revalidation, and cancel the view on page close, window close or person-session loss; `new native/desktop/src-tauri/src/shell/sede_view.rs, native/desktop/src-tauri/src/shell/mod.rs, native/desktop/src-tauri/src/shell/external.rs, native/application/src/person_operations.rs, src-tauri capability and command registration`.

### Phase `P04` - desktop Browser page

Deliver the Browser page, the Browser and AEAT rail items with the AEAT context menu, palette actions, the register element, locale keys in four languages and scenario coverage.

- [ ] `P04.S09` - add the Browser page: canvas drawing from in-memory JPEG bytes with credit after draw, terminal-scope key capture, pointer, wheel and text forwarding, the toolbar with origin and path display, notices, external offers, page dialogs and the busy guard while publishing; `new native/desktop/frontend/src/components/browser/, native/desktop/frontend/src/shell/navigation/windowViews.ts, native/desktop/frontend/src/ipc/contract.ts, native/desktop/frontend/src/ipc/tauriHost.ts`.
- [ ] `P04.S10` - add the Browser rail item, the AEAT rail click to the Browser page with its Open in external browser context menu, both palette actions, the gui register element and its regenerated projection, and the locale keys in four languages through the canonical locale workflow; `native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/Rail.tsx, native/desktop/frontend/src/shell/actions.ts, src/cadrumo_client/contracts/navigation.toml, src/cadrumo_client/contracts/tests/navigation_shipped_views.json, src/cadrumo/locales/{en,es,ca,hu}/common.yml, dev/locales/desktop_chrome.py`.
- [ ] `P04.S11` - add scenario host fixtures for a synthetic view and a sede-browser scenario spec covering the rail, the AEAT context menu, toolbar verbs, key scope, notices and offers, the publish busy guard and close cancellation; `native/desktop/frontend/src/dev/scenarioHost.ts, new native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`.

### Phase `P05` - in-panel login

Deliver certificate and Cl@ve Movil login inside the view's own headless Chromium, shown through the stream, with Cl@ve Permanente reported unavailable until grounded.

- [ ] `P05.S12` - run certificate and Cl@ve Movil login inside the view's headless Chromium shown through the stream, skip the forced headed browser only when a view is attached, refuse input while acquiring, publish at once on success, and report Cl@ve Permanente unavailable with an external offer; `src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py, src/cadrumo/adapters/outbound/aeat/auth/providers.py, src/cadrumo/adapters/outbound/aeat/auth/authenticator.py, src/cadrumo/application/live/sede_view_operation.py, auth tests`.

### Phase `P06` - integrated verification

Prove the lane, the guard, session sharing and redaction across all legs, then an attended end-to-end check against the real Sede on a non-installer development build.

- [ ] `P06.S13` - add a cross-leg integration test with a real worker, runtime host and Rust lane against synthetic Sede pages fulfilled behind the guard, proving attach binding, credit, latest-wins, unbinding on sign-out, guard refusals and that no frame, URL or input reaches logs, journals or projections; `new src/cadrumo_runtime/host/tests/test_view_stream_integration.py, native/application view stream integration test`.
- [ ] `P06.S14` - run the attended end-to-end check on a non-installer development build against the real Sede: log in in the panel then reuse it from an aeat CLI live read, log in from the CLI then open the panel signed in, and confirm refusal offers and close-time publication, recording evidence in the ledger; `development build targets and the plan ledger, no product files`.

## Parallelization

Hard ordering:

- P01.S01 lands first: its control models and `view_stream_vectors.json` are the contract P01.S02, P01.S03, P02.S06, P02.S07 and P03.S08 consume.
- P01.S02 precedes P02.S07, which wires the operation onto the worker view channel. The executor reaches that channel only through a typed sink port the host composes into the operation context; the tax package never imports `cadrumo_runtime`.
- P02.S04 and P02.S05 precede P02.S07. P02.S06 precedes P02.S07.
- P01.S03 precedes P03.S08. P03.S08 precedes P04.S09, which consumes the host commands and channel messages.
- P04.S09 precedes P04.S10 and P04.S11. P04.S10 precedes P04.S11.
- P05.S12 needs P02.S07 complete.
- P06.S13 needs P01 to P05 complete. P06.S14 runs last, after P06.S13, with the operator present.

Parallel lanes with disjoint write ownership, after P01.S01:

- Lane A (runtime and Rust transport): P01.S02, then P01.S03. Owns `src/cadrumo_runtime/host/` and `native/application/src/runtime_client.rs`, `view_stream.rs`, `lib.rs`.
- Lane B (Python browser adapter and auth): P02.S04, P02.S05 and P02.S06 in parallel with each other only if their files stay disjoint. S04 owns `browser/session.py`, `request_guard.py` and `remote_state_guard.py`. S05 owns `application/auth/sessions.py`, `application/live/session.py`, `auth/authenticator.py` and `auth/session_store.py`. S06 owns `browser/screencast.py` and `browser/view_input.py`. A page-observer hook needed by S06 is added by S04, so S06 rebases on S04 before closing.
- Lane C joins after A and B: P02.S07, then P05.S12 (both own `application/live/sede_view_operation.py`, so they are serial).
- Lane D (desktop): P03.S08, then P04.S09, P04.S10 and P04.S11 serially. Owns `native/desktop/`. P04.S10 also writes `src/cadrumo_client/contracts/navigation.toml`, the locale catalogues and `dev/locales/desktop_chrome.py`, which other sessions edit concurrently: re-read before patching and commit by pathspec. P03.S08 touches `native/application/src/person_operations.rs` only after lane A has closed P01.S03.

Suggested executors (architecture-level: opus, medium effort; bounded: sonnet, xhigh effort):

| Step | Executor |
|---|---|
| P01.S01 | opus medium |
| P01.S02 | opus medium |
| P01.S03 | sonnet xhigh |
| P02.S04 | opus medium |
| P02.S05 | opus medium |
| P02.S06 | sonnet xhigh |
| P02.S07 | opus medium |
| P03.S08 | sonnet xhigh |
| P04.S09 | sonnet xhigh |
| P04.S10 | sonnet xhigh |
| P04.S11 | sonnet xhigh |
| P05.S12 | opus medium |
| P06.S13 | opus medium |
| P06.S14 | opus medium |

## Verification

Per-Step checks. Each Step also runs `just check-style`, `just check-format` and `just check-types` on its scope, and `just check-import-boundaries` when it adds or moves an import. Native code builds and tests only through CMake targets; nothing calls cargo directly, and no installer or MSI target is built.

- P01.S01: `uv run --no-sync pytest src/cadrumo_client/transport/tests src/cadrumo_client/contracts/tests`. Required evidence: header round trip at the 65,520-byte and 2 MiB bounds; refusal of an out-of-order chunk, an interleaved image, an oversize image and a `B` frame on a document reader; the vectors file is regenerated by its owner, not hand-edited.
- P01.S02: `uv run --no-sync pytest src/cadrumo_runtime/host/tests -k view`. Required evidence: an attach from another session, another profile, another native peer, a reused token and an expired token each refused; unbinding on sign-out, lock, operation end and person-connection close happens before worker settlement; with no window credit no image is buffered.
- P01.S03: `just check-rust`, then `just test-native-bundle Debug`. Required evidence: the Rust reader passes the shared vectors and refuses the same violations as Python.
- P02.S04: `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests src/cadrumo/domain/calculations/registry/tests -k "guard or view"`. Required evidence, through the real guard and real headless Chromium: a POST not declared, a GET with a forbidden token, an off-host subresource, a service worker registration and a WebSocket are refused; an off-host top-level navigation, a popup, a download and a file chooser produce offers; an empty policy set refuses everything.
- P02.S05: `uv run --no-sync pytest src/cadrumo/application/auth/tests src/cadrumo/application/live/tests -k "view or session"`. Required evidence: identity mismatch publishes nothing; a stored digest changed by another acquisition yields kept-newer and leaves it intact; an interruption after the `UNKNOWN` report stays unknown; the acquisition lock is not held while browsing.
- P02.S06: `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/browser/tests -k "screencast or input"`. Required evidence: frames stop without credit and resume with the newest image; out-of-range coordinates, oversized text and unknown variants are refused; no `evaluate` call exists in the adapter, checked by a static test.
- P02.S07: `uv run --no-sync pytest src/cadrumo/application/live/tests -k sede_view`, `just check-operation-contract-manifest`. Required evidence: MCP and non-desktop sessions are refused; cancel and idle expiry reach the closing phase; the journal holds no URL, title, frame or input.
- P03.S08: `just check-rust`, `just test-native-bundle Debug`. Required evidence: every command refuses a bad token; an offer id not issued by the host is refused; page close, window close and session loss cancel the view.
- P04.S09 to P04.S11: in `native/desktop/frontend`, `npm run check` and `npx playwright test tests/scenarios/sede-browser.spec.ts tests/scenarios/navigation-register.spec.ts tests/scenarios/palette.spec.ts`; `just check-locales`. Required evidence: no frame, URL or title reaches localStorage or the documentation frame; the AEAT context menu opens the external browser; the AEAT click opens the Browser page.
- P05.S12: `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests -k "view or headless"`. Required evidence: the CLI's Cl@ve Movil path keeps its forced headed browser when no view is attached; input is refused while acquiring.
- P06.S13: `uv run --no-sync pytest src/cadrumo_runtime/host/tests/test_view_stream_integration.py` and the native integration target through `just test-native-bundle Debug`. Required evidence: a redaction scan over logs, journals, projections and diagnostics after a scripted session finds no frame bytes, URL query, title or typed text.
- P06.S14: attended by the operator on a development build. Recorded in the ledger: a panel login reused by an `aeat` live read with no new login, a CLI login adopted by a newly opened panel, at least one refusal offer, and the close-time publication outcome.

The plan is complete when every Step is closed, each Phase-close review and the final integrated review pass, and pending verification is reported apart from defects.
