---
tags:
  - '#adr'
  - '#sede-browser'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:0cd290bb31847c6ba1b651c03ed0343536eef98d26d5689fe17e4be3258da734'
related:
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-03-aeat-live-write-guard-adr]]"
  - "[[2026-06-04-live-auth-decomposition-adr]]"
  - "[[2026-07-16-protected-browser-certificate-auth-adr]]"
  - "[[2026-07-10-clave-permanente-idp-guard-host-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-10-18-runtime-authority-boundary-adr]]"
  - "[[2026-07-21-desktop-capture-harness-adr]]"
  - '[[2026-10-27-sede-browser-reference]]'
---

# `sede-browser` adr: `in-app AEAT Sede browser by screencast` | (**status:** `accepted`)

## Problem Statement

The user asked on 2026-10-27 for an in-app browser in the desktop window: a Browser rail button, the AEAT Sede as its default page, and an AEAT rail button whose click opens that browser and whose context menu offers the external browser. The browser must share exactly the AEAT authentication of the CLI and TUI syncs. Offered three shapes, the user chose "stream our Chromium's page into a panel" and said "implement 1)".

The window may load nothing remote (`2026-10-04-desktop-shell-adr`), every browser-context request must pass the remote-state guard (`2026-10-03-aeat-live-write-guard-adr`), AEAT session state lives only in encrypted custody (`2026-06-04-live-auth-decomposition-adr`), and no binary stream exists anywhere in the runtime transport. This record decides how a person-driven, long-lived browser view fits those rulings, and the stream protocol it needs.

## Considerations

Grounding locators are collected in `2026-10-27-sede-browser-reference`.

- Chromium is provisioned in full and as headless shell (`native/application/src/provisioning/browser.rs:919`); Python points Playwright at it (`src/cadrumo/adapters/outbound/aeat/browser/factory.py:459`). Each live operation owns its own browser through `own_provider_browser` (`src/cadrumo/application/live/live_operation_execution.py:61`) and the process-owned resource scope (`factory.py:108`); no browser outlives an operation.
- Authenticated state enters a context only at `new_context(storage_state=...)`, with the certificate injected in `_build_context_kwargs` (`src/cadrumo/adapters/outbound/aeat/browser/session.py:341`). Post-hoc context mutation is ruled out (`2026-06-04-live-auth-decomposition-adr`).
- Session custody is the encrypted per-provider storage state (`src/cadrumo/adapters/outbound/aeat/auth/session_store.py`), staged through `defer_writes()` and published only after a guarded acquisition (`src/cadrumo/application/live/session.py:57`). The stored metadata carries `storage_state_sha256` (`src/cadrumo/adapters/outbound/aeat/auth/authenticator.py:690`). Reuse and acquisition run through `ensure_authenticated_aeat_session` (`src/cadrumo/application/auth/sessions.py:338`) under the acquisition lock (`src/cadrumo/application/auth/acquisition_lock.py:288`).
- Live definitions are non-interactive, cancellation `UNSUPPORTED`, deadline `ABSENT` (`src/cadrumo/application/live/live_operation_registration.py:32`, `src/cadrumo/application/operations/capabilities.py:342`). The supervisor leases for 10 minutes and bounds execution to one hour (`src/cadrumo/entrypoints/operation_composition.py:98-99`). `OperationCancellation.COOPERATIVE` and `OperationClosePolicy.REQUEST_CANCEL` exist (`src/cadrumo/core/operations.py:115`, `:131`).
- The context-wide guard of `2026-10-03-aeat-live-write-guard-adr` ruling 4 is not built: plan step S02 of `2026-09-24-aeat-live-write-guard-plan` is open, and the only page-wide route today is `src/cadrumo/adapters/outbound/aeat/sede/censal_navigation.py:70`.
- Frames are at most 64 KiB, kinds `J`, `E` and `S` (`src/cadrumo_client/transport/frame_io.py:38-48`); both readers refuse any other kind (`frame_io.py:100`, `native/application/src/runtime_client.rs:316`), and each reply frame has a 5 s budget (`runtime_client.rs:50`). The window holds its own person session on a native connection (`2026-10-04-application-sign-in-adr`, amendment 2026-10-24) and drives registered operations through `native/application/src/person_operations.rs`.
- Cl@ve Móvil forces a headed browser for its QR (`src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:708`). Cl@ve Permanente stays refused at context level until its requests are grounded (`2026-10-03-aeat-live-write-guard-adr` ruling 5).
- Playwright 1.64 (`uv.lock`) offers `BrowserContext.new_cdp_session`, `service_workers="block"` and `route_web_socket`.
- `2026-07-21-desktop-capture-harness-adr` governs a CDP harness attached to Claude Desktop through a remote-debugging port. It makes no product-wide CDP ruling.

## Considered options

- **Stream the worker's own Chromium page into a canvas (chosen by the user).** The browser stays in the profile worker under the existing custody, guard and operation ownership; the window receives pixels only.
- **Load the Sede in a Tauri webview or iframe (rejected).** Breaks "nothing remote loads in the webview" and the closed CSP, and the webview's cookie jar would be a second, plaintext custody that cannot share the encrypted storage state.
- **Launch a headed Chromium window beside the desktop (rejected).** Not in-app, and the person's input would bypass the panel's input bounds; it is the CLI's Cl@ve Móvil behaviour, kept there.
- **Ship storage state to the window or the system browser (rejected).** Puts cookies outside encrypted custody, forbidden by `2026-06-04-live-auth-decomposition-adr`.
- **Carry frames on the person connection or as `J` document transfers (rejected).** Base64 documents with a 1 MiB transfer cap (`runtime_client.rs:52`) and a 5 s frame budget would let video starve replies and session events.
- **A remote-debugging port or a CDP endpoint the window talks to (rejected).** An open port is reachable by every same-user process and grants script evaluation.

## Constraints

**Operation.**
- The view is one registered operation, `live.sede.view`, run in the profile worker. It owns its Chromium through the existing process-owned resource scope; no browser outlives it.
- Admission: a human-kind session on the desktop frontend only. It is not projected to MCP and has no CLI or TUI command, because only the window consumes the stream. No agent drives it.
- Its own capability set: cancellation `COOPERATIVE`, close policy `REQUEST_CANCEL`, replay none, owned resource `PROCESS`, credential-free request journal, conflict scope one view per profile. Lifetime is bounded by an idle expiry with no person input and an absolute bound within the supervisor's execution timeout. Both are enforced by the executor, and the view also ends when the window's person session is retired (sign-out, lock, idle, generation change) or the window closes.
- The request carries only the panel size and scale. The start page is the backend's `aeat.domains.sede` (`src/cadrumo/core/external_constants.toml:13`), never a window-supplied URL.
- The view enters through `AeatAccessGate.require_live_read` and the canonical acquisition path. There is no second session loader.

**Session sharing.**
- The view seeds its context from the same encrypted storage-state custody the CLI and TUI syncs use, through `new_context(storage_state=...)` with the configured provider's certificate provisioning. It holds the acquisition lock only while acquiring and while publishing, never for its whole life, so syncs keep running beside it, each in its own Chromium seeded from the same custody.
- With no valid stored session, the configured provider's existing login runs inside the view's Chromium, headless, and the person watches it through the stream. During this phase the view is view-only and refuses input with a notice. Cl@ve Móvil's QR is shown in the panel; the forced headed browser applies only when no view is attached. A login that succeeds publishes through the same deferred session writes as any sync, so the CLI and TUI reuse it at once.
- At close, cancel or expiry the view captures storage state from its context through the provider's own capture, runs the provider's verification including active-profile identity alignment, and publishes through the same deferred writes, under the effect guard, only if verification succeeds and the stored `storage_state_sha256` still equals the digest it was seeded from or last published. Typed outcomes: published, unchanged, kept-newer (another acquisition published meanwhile, and it stands), verification-failed (nothing published, nothing deleted), and unknown (interrupted between the `UNKNOWN` and `UPDATED` effect reports).
- A running view is never re-seeded; a session published elsewhere is adopted on the next open.
- "Exactly the same session" means the same custody and the same cookies and local storage. Session storage and in-memory page state are per process and never transferred, as between syncs today.

**Guard.**
- The view's context is created with the public composition module of `2026-10-03-aeat-live-write-guard-adr` ruling 4 installed before any page exists, evaluating every request against the union of the operator-view policy and the configured provider's auth policy. No bypass, no observe mode, no per-call override.
- The operator-view policy, as amended into that record: AEAT hosts from `[aeat.domains]` and the Cl@ve IdP apex; GET and HEAD on any path, still subject to the whole-URL forbidden-token scan and forbidden actions; POST only as exact declared read requests already grounded under ruling 5.
- Every refused request is aborted and reported to the panel as a notice. A refused top-level navigation, a popup to another host, a download (`accept_downloads=False` stays) and a file chooser each become an "open in external browser" offer. Service workers are blocked and WebSockets closed. The view issues no Playwright API requests.
- The system browser receives only a URL, through the host's existing `open_external` admission, and never a session.

**Screencast and input.**
- Pixels come from a CDP session on the view's own page (`new_cdp_session`) with `Page.startScreencast` as JPEG, sized to the panel and capped. The worker acknowledges each CDP frame at once and keeps only the newest unsent image.
- Input reaches the page only as CDP `Input.dispatchMouseEvent`, `Input.dispatchKeyEvent` and `Input.insertText`, plus the verbs back, forward, reload and home. No script is evaluated on the person's behalf, and no remote-debugging port is opened.
- Inputs are closed typed variants with clamped coordinates, a bounded rate (pointer moves coalesced) and bounded text. Excess is dropped, never queued.
- This is product use of a Playwright-owned CDP session, outside the scope of `2026-07-21-desktop-capture-harness-adr`, which therefore needs no amendment.

**Stream lane.**
- A dedicated verified connection per view on each leg: worker to runtime host on a worker view channel beside the control and operation channels, and runtime host to window on a view connection beside the person connection. Neither leg multiplexes onto an existing channel.
- One new frame kind `B` (binary chunk) is legal only on view connections; `J` carries their control documents. `S` and `E` never appear on them, and every other connection keeps refusing `B`.
- A `B` payload is a 16-byte header (version 1, flags with bit 0 marking the last chunk, two reserved zero bytes, image sequence u32, chunk index u16, chunk count u16, image length u32, network order) followed by at most 65,520 bytes. One image is at most 2 MiB, its chunks contiguous and in order, announced by a `view.image` control document with sequence, pixel size, CSS size and scale. Anything else is a protocol violation that closes the view connection.
- Downstream control documents: `view.image`, `view.state` (URL origin and path only, title, back and forward availability, loading, phase), `view.notice` (closed codes, with an offer id where an external open is offered) and `view.closed` with its reason. Upstream: `view.credit`, `view.input`, `view.navigate`, `view.resize`, `view.dialog`. Field names are hypotheses; the closed sets and bounds are not.
- Backpressure is credit of at most two images per leg, granted by the window after drawing. A producer without credit replaces its pending image. Nothing is buffered beyond that.
- Binding: on its person connection the window asks to attach to an operation id. The host checks that the operation is a running `live.sede.view` submitted by that same admitted desktop session (profile, session, native peer, boot) and returns a single-use attach token of at least 32 CSPRNG bytes that expires in 10 seconds. The window presents it, compared in constant time, as the first document on a new view connection from the same native peer. One view connection is bound per operation; a later attach replaces it. The host unbinds immediately when the operation ends, the session is retired, the person connection closes, a violation occurs or the runtime stops, without waiting for the worker to settle. The worker channel is bound to one running operation that worker owns.
- Frames, page titles, URLs and input are private taxpayer data. They are never logged, persisted, cached, journaled, put in projections, results or diagnostics, or sent to the documentation frame. They live in memory only, with Rust buffers zeroized on drop; Python and WebView copies cannot be wiped, and this record says so.

**Window.**
- The page draws on a canvas from in-memory bytes. The webview loads no remote resource, and the CSP is unchanged.
- Closed token-checked host commands open, input, navigate, resize, credit, answer a dialog, open the current offer externally (the window sends only an offer id; the host holds the URL and revalidates it) and close. The host relays the stream on one Tauri `Channel` delivered to the top document only.
- The toolbar shows back, forward, reload, home, the page's origin and path (never its query, and there is no URL entry), and open-externally.
- The rail gains Browser. A click on the AEAT rail item opens the Browser page at the Sede; its context menu offers "Open in external browser", which is the existing `link.aeat` action. The palette offers both. While the canvas has focus it receives keys as a terminal does: only the shell's everywhere chords are reserved.
- Leaving the page keeps the view running without frames; closing the page or the window cancels it. The navigation guard reports the page `busy` only while the view publishes.
- Wording comes from the canonical locale workflow in four languages, in the informal singular.

**Scope.** Browse and log in only. Form submissions, uploads, signing and presentation stay refused, and the person is offered the external browser. Watching a running sync in the panel is out of scope.

## Implementation

We will add the `live.sede.view` operation, the context-wide guard composition module installed on the view's context, the view stream lane on both legs, and the desktop Browser page, sequenced in `2026-10-27-sede-browser-plan`. The guard module is the one ruling 4 of `2026-10-03-aeat-live-write-guard-adr` names: the view lands it fail-closed on its own new context, and S02 of that record's plan later installs it on every context once the declared reads are grounded. Hypotheses that may change within the constraints: field and command names, idle expiry (about 15 minutes), the screencast's size cap, JPEG quality and frame rate, input rates, the worker view channel's endpoint namespace, the page-observer hook through which the browser session exposes the provider's login pages to the screencast, and the icon.

Open follow-up, needing the user's approval: allow full human use of the Sede in the panel, including submission and signing. That would be the first person-originated write path, and it needs its own amendment of `2026-10-03-aeat-live-write-guard-adr` and of `AeatAccessGate.require_live_write` (`src/cadrumo/core/access_gate/gate.py:96`), which refuses every live write today. Also deferred: watching a sync live, and copying text out of the page, which would need script evaluation.

Accepted 2026-10-27 on the user's choice, in this session, of "stream our Chromium's page into a panel" and "implement 1)", with the defaults recorded above for the unanswered clarifying question: browse and log in only, off-AEAT links in the system browser, and session sharing through the same custody.

## Rationale

The screencast keeps the browser where custody, the guard and operation ownership already live. The window gains pixels and a bounded input channel, never a cookie, a remote document or a debugging endpoint. That is the only shape that satisfies "same session as the CLI and TUI" and "nothing remote in the webview" together: a webview would need its own cookie jar, and shipping storage state anywhere breaks the custody rule. Seeding from custody and publishing back through the deferred writes reuses the one publication path, so the panel and the syncs agree without a second loader. The digest precondition keeps the panel from overwriting a newer acquisition. Holding the lock only around acquisition and publication keeps syncs usable while a view is open.

A dedicated connection per leg keeps video from competing with replies and session events and lets backpressure drop images instead of blocking. A single new frame kind confined to those connections leaves every existing reader's refusal intact. The attach token and same-peer check bind the lane to the exact session that started the view, as the runtime binds every other act.

## Consequences

- Good: the person can browse the Sede and log in inside Cadrumo, and a login there is reused by every CLI, TUI and desktop sync at once.
- Good: the view is the first consumer of the context-wide guard; its notices show which Sede requests are not yet grounded.
- Cost: Sede pages that need an ungrounded POST, or whose URL carries a forbidden token (for example presentation pages), are refused and offered externally. The external browser has no Cadrumo session, so the person logs in again there.
- Cost: a GET that changes remote state without a forbidden token is not caught by the guard. This is the same residual risk the read guard already carries.
- Cost: Cl@ve Permanente login in the panel stays unavailable until its requests are grounded.
- Cost: a new runtime protocol lane, a new frame kind and a long-lived interactive operation class to maintain and test on every platform. Python and WebView copies of frames cannot be wiped.
- Reconsider if the guard cannot observe a class of requests the Sede issues, if CDP screencast proves too slow at panel sizes, or if the user approves full human use.
