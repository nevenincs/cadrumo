---
tags:
  - '#adr'
  - '#sede-browser'
date: '2026-10-27'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:7ed47dc77fa5f4aa4e63eb576f8899f3e631ef0a2e87c2faee6ebe839c2784c6'
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

The user ruled on 2026-10-27 that the in-app browser is free use: "I do not understand how we could limit usage - its a browser, free usage. I would not attempt to restrict or define limits, it should not be technically enforceable."

The window may load nothing remote (`2026-10-04-desktop-shell-adr`), every request Cadrumo initiates must pass the remote-state guard (`2026-10-03-aeat-live-write-guard-adr`), AEAT session state lives only in encrypted custody (`2026-06-04-live-auth-decomposition-adr`), and no binary stream exists anywhere in the runtime transport. This record decides how a human-driven, unrestricted, long-lived browser view fits those rulings, and the stream protocol it needs.

## Considerations

Grounding locators are collected in `2026-10-27-sede-browser-reference`.

- Chromium is provisioned in full and as headless shell (`native/application/src/provisioning/browser.rs:919`); Python points Playwright at it (`src/cadrumo/adapters/outbound/aeat/browser/factory.py:459`). Each live operation owns its own browser through `own_provider_browser` (`src/cadrumo/application/live/live_operation_execution.py:61`) and the process-owned resource scope (`factory.py:108`); no browser outlives an operation.
- Authenticated state enters a context only at `new_context(storage_state=...)`, with the certificate injected in `_build_context_kwargs` (`src/cadrumo/adapters/outbound/aeat/browser/session.py:341`). Post-hoc context mutation is ruled out (`2026-06-04-live-auth-decomposition-adr`).
- Session custody is the encrypted per-provider storage state (`src/cadrumo/adapters/outbound/aeat/auth/session_store.py`), staged through `defer_writes()` and published only after a guarded acquisition (`src/cadrumo/application/live/session.py:57`). The stored metadata carries `storage_state_sha256` (`src/cadrumo/adapters/outbound/aeat/auth/authenticator.py:690`). Reuse and acquisition run through `ensure_authenticated_aeat_session` (`src/cadrumo/application/auth/sessions.py:338`) under the acquisition lock (`src/cadrumo/application/auth/acquisition_lock.py:288`).
- Live definitions are non-interactive, cancellation `UNSUPPORTED`, deadline `ABSENT` (`src/cadrumo/application/live/live_operation_registration.py:32`, `src/cadrumo/application/operations/capabilities.py:342`). The supervisor leases for 10 minutes and bounds execution to one hour (`src/cadrumo/entrypoints/operation_composition.py:98-99`). `OperationCancellation.COOPERATIVE` and `OperationClosePolicy.REQUEST_CANCEL` exist (`src/cadrumo/core/operations.py:115`, `:131`).
- The guard of `2026-10-03-aeat-live-write-guard-adr` evaluates the requests Cadrumo's readers and logins issue; its context-wide route (ruling 4) is plan step S02 of `2026-09-24-aeat-live-write-guard-plan`, still open. `AeatAccessGate.require_live_write` refuses every Cadrumo live write (`src/cadrumo/core/access_gate/gate.py:96`).
- Frames are at most 64 KiB, kinds `J`, `E` and `S` (`src/cadrumo_client/transport/frame_io.py:38-48`); both readers refuse any other kind (`frame_io.py:100`, `native/application/src/runtime_client.rs:316`), and each reply frame has a 5 s budget (`runtime_client.rs:50`). The window holds its own person session on a native connection (`2026-10-04-application-sign-in-adr`, amendment 2026-10-24) and drives registered operations through `native/application/src/person_operations.rs`.
- Cl@ve Móvil forces a headed browser for its QR (`src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:708`). Cadrumo-driven Cl@ve Permanente login stays refused at context level until its requests are grounded (`2026-10-03-aeat-live-write-guard-adr` ruling 5); a person typing into a page is not a Cadrumo-driven login.
- Playwright 1.64 (`uv.lock`) offers `BrowserContext.new_cdp_session`, page `popup`, `download` and `filechooser` events, `FileChooser.set_files` with in-memory payloads, and `accept_downloads`.
- `2026-07-21-desktop-capture-harness-adr` governs a CDP harness attached to Claude Desktop through a remote-debugging port. It makes no product-wide CDP ruling.

## Considered options

- **Stream the worker's own Chromium page into a canvas (chosen by the user).** The browser stays in the profile worker under the existing custody and operation ownership; the window receives pixels only.
- **Load the Sede in a Tauri webview or iframe (rejected).** Breaks "nothing remote loads in the webview" and the closed CSP, and the webview's cookie jar would be a second, plaintext custody that cannot share the encrypted storage state.
- **Launch a headed Chromium window beside the desktop (rejected).** Not in-app; it is the CLI's Cl@ve Móvil behaviour, kept there.
- **Ship storage state to the window or the system browser (rejected).** Puts cookies outside encrypted custody, forbidden by `2026-06-04-live-auth-decomposition-adr`.
- **Carry frames on the person connection or as `J` document transfers (rejected).** Base64 documents with a 1 MiB transfer cap (`runtime_client.rs:52`) and a 5 s frame budget would let video starve replies and session events.
- **A remote-debugging port or a CDP endpoint the window talks to (rejected).** An open port is reachable by every same-user process and grants script evaluation.

## Constraints

**Operation.**
- The view is one registered operation, `live.sede.view`, run in the profile worker. It owns its Chromium through the existing process-owned resource scope; no browser outlives it.
- Admission: a human-kind session on the desktop frontend only. It is not projected to MCP and has no CLI or TUI command, because only the window consumes the stream. No agent drives it.
- Its own capability set: cancellation `COOPERATIVE`, close policy `REQUEST_CANCEL`, replay none, owned resource `PROCESS`, credential-free request journal, conflict scope one view per profile, and no execution deadline. The view lives while the window is open and the person session is held; leaving the Browser page does not close it. It ends when the panel or window closes or when that session is retired (sign-out, lock, generation change). It sets no idle or absolute limit of its own. Closing the panel or window is not a cancellation: the window sends the upstream `view.close` document, and a view connection that drops without one is closed the same way. The supervisor's cancel covers session loss, lock and runtime stop, and stops the view without publishing.
- The request carries only the panel size and scale. The start page is the backend's `aeat.domains.sede` (`src/cadrumo/core/external_constants.toml:13`), never a window-supplied URL.
- The view enters through `AeatAccessGate.require_live_read` and the canonical acquisition path. There is no second session loader.

**Session sharing.**
- The view seeds its context from the same encrypted storage-state custody the CLI and TUI syncs use, through `new_context(storage_state=...)` with the configured provider's certificate provisioning. It holds the acquisition lock only while acquiring and while publishing, never for its whole life, so syncs keep running beside it, each in its own Chromium seeded from the same custody.
- With no valid stored session the person may simply log in in the panel by hand, with any provider, Cl@ve Permanente included. The configured provider's existing certificate or Cl@ve Móvil login can also run inside the view's Chromium, headless, as assistance the person watches through the stream; Cl@ve Móvil's QR is shown in the panel, and the forced headed browser applies only when no view is attached. While an assisted step runs, the view may hold off the person's input only if the person can always interrupt it, which stops the step and returns input at once.
- After any login in the panel, manual or assisted, the view captures storage state through the provider's own capture, publishes once the provider's verification passes, including that the signed-in taxpayer is the profile's, through the same deferred session writes as any sync, so the CLI and TUI reuse it at once.
- At a graceful close (the window's `view.close`, the view connection dropping without one, or the view's last page closing) the view captures and verifies the same way and publishes, under the effect guard, only if verification succeeds and the stored `storage_state_sha256` still equals the digest it was seeded from or last published. Typed outcomes: published, unchanged, kept-newer (another acquisition published meanwhile, and it stands), verification-failed (nothing published, nothing deleted), identity-mismatch (the censal NIF of the signed-in taxpayer differs from the profile's: nothing is published and the window shows the `identity_mismatch` notice), and unknown (interrupted between the `UNKNOWN` and `UPDATED` effect reports). The view then settles as succeeded with that typed outcome in its result, which carries no URL, title or bytes. A supervisor cancel, and the host ending the view channel because the session was retired or locked or the runtime stops, end the view without this publication; a login made in the panel publishes when it completes.
- A running view is never re-seeded; a session published elsewhere is adopted on the next open.
- "Exactly the same session" means the same custody and the same cookies and local storage. Session storage and in-memory page state are per process and never transferred, as between syncs today.

**Human-driven, unrestricted.**
- The view is a browser the person drives freely. Any site loads in the panel. Nothing is filtered or blocked: no request route, method or host policy, service-worker or WebSocket block, or forced external open is installed on its context. Form submission, upload, download, signing and presentation work as in any browser.
- Cadrumo issues no request in the view: it never scripts the page, never evaluates script in it and issues no Playwright API request from it. Only the person's forwarded input acts. The live-write guard of `2026-10-03-aeat-live-write-guard-adr` therefore has no Cadrumo request to evaluate there, and it stays unchanged for every request Cadrumo initiates, including the assisted login steps above. `AeatAccessGate.require_live_write` still refuses every Cadrumo submission.
- A popup opens in the view; the panel shows the newest page, and closing it returns to its opener. Page dialogs are answered by the person.
- A download opens the host's native save dialog, and its bytes go only to the path the person picks; Chromium's own transient download file is deleted when the transfer ends. A file chooser opens the host's native open dialog, and the chosen file reaches the page as an in-memory payload. Neither enters Cadrumo custody unless the person chooses to import it there.
- "Open in external browser" is a person's action, in the AEAT rail context menu and in the toolbar. The system browser receives only a URL, through the host's `open_external`, and never a session.

**Screencast and input.**
- Pixels come from a CDP session on the view's own page (`new_cdp_session`) with `Page.startScreencast` as JPEG, sized to the panel and capped. The worker acknowledges each CDP frame at once and keeps only the newest unsent image.
- Input reaches the page only as CDP `Input.dispatchMouseEvent`, `Input.dispatchKeyEvent` and `Input.insertText`, plus the verbs back, forward, reload and home. No remote-debugging port is opened.
- Inputs are closed typed variants with clamped coordinates. The worker applies every event as sent; the desktop host coalesces pointer moves.
- This is product use of a Playwright-owned CDP session, outside the scope of `2026-07-21-desktop-capture-harness-adr`, which therefore needs no amendment.

**Stream lane.**
- A dedicated verified connection per view on each leg: worker to runtime host on a worker view channel beside the control and operation channels, and runtime host to window on a view connection beside the person connection. Neither leg multiplexes onto an existing channel.
- One new frame kind `B` (binary chunk) is legal only on view connections; `J` carries their control documents. `S` and `E` never appear on them, and every other connection keeps refusing `B`.
- A `B` payload is a 16-byte header (version 1, flags with bit 0 marking the last chunk, two reserved zero bytes, image sequence u32, chunk index u16, chunk count u16, image length u32, network order) followed by at most 65,520 bytes. One image is at most 2 MiB, its chunks contiguous and in order, announced by a `view.image` control document with sequence, pixel size, CSS size and scale. Anything else is a protocol violation that closes the view connection.
- Download and upload bytes travel on the same view lane under credit, announced by their own control documents; their chunk framing keeps every existing refusal.
- Downstream control documents: `view.image`, `view.state` (origin and path for the toolbar, the page's full address for the desktop host alone, title, back and forward availability, loading, phase), `view.notice` (closed codes), `view.download` and `view.file_chooser` requests, and `view.closed` with its reason. Upstream: `view.credit`, `view.input`, `view.navigate`, `view.resize`, `view.dialog`, `view.close` and the transfer answers. Field names are hypotheses; the closed sets are not.
- Backpressure is credit of at most two images per leg, granted by the window after drawing. A producer without credit replaces its pending image. Nothing is buffered beyond that.
- Binding: on its person connection the window asks to attach to an operation id. The host checks that the operation is a running `live.sede.view` submitted by that same admitted desktop session (profile, session, native peer, boot) and returns a single-use attach token of at least 32 CSPRNG bytes that expires in 10 seconds. The window presents it, compared in constant time, as the first document on a new view connection from the same native peer. One view connection is bound per operation; a later attach replaces it. The host unbinds immediately when the operation ends, the session is retired, the person connection closes, a violation occurs or the runtime stops, without waiting for the worker to settle. The worker channel is bound to one running operation that worker owns.
- Frames, page titles, URLs, input and transferred file bytes are private taxpayer data. They are never logged, persisted, cached, journaled, put in projections, results or diagnostics, or sent to the documentation frame. They live in memory only, with Rust buffers zeroized on drop; Python and WebView copies cannot be wiped, and this record says so.

**Window.**
- Images reach the webview as raw binary and the page draws on a canvas from those in-memory bytes. The webview loads no remote resource, and the CSP is unchanged.
- Closed token-checked host commands open, input, navigate, resize, credit, answer a dialog, answer a download or file chooser through the native save or open dialog, open the current page externally (the window sends no URL; the host opens the page's full address, which it holds from the worker leg and never forwards to the window) and close. The host relays the stream on one Tauri `Channel` delivered to the top document only.
- The toolbar shows back, forward, reload, home, the page's origin and path (never its query, and there is no URL entry), and "Open in external browser".
- The rail gains Browser. A click on the AEAT rail item opens the Browser page at the Sede; its context menu offers "Open in external browser", which is the existing `link.aeat` action. The palette offers both. While the canvas has focus it receives keys as a terminal does: only the shell's everywhere chords are reserved.
- Leaving the Browser page keeps the view running without frames. Closing the panel or the window sends `view.close`, which publishes the session and ends the view; a supervisor cancel does not publish. The navigation guard reports the page `busy` only while the view publishes, so a publication is not cut off.
- Closing the window while a view is open never freezes it. The host hides the window at once and stops answering activation, sends `view.close`, and waits on a thread of its own for the view to end. Only then does it close the window again, so sign-in retires the person session after the close-time publication, and the application exits. The wait is bounded by the relay's settle limit of 90 seconds, counted from the first close request; it bounds shutdown and is not a usage limit. A close asked for again during the wait joins it. A second launch meanwhile waits for the instance lock within its usual patience instead of activating the closing window. An OS session end exits the process at once and does not wait for the publication. The desktop has no tray or background mode.
- Wording comes from the canonical locale workflow in four languages, in the informal singular.

**Scope.** Watching a running sync in the panel is out of scope.

## Implementation

We will add the `live.sede.view` operation with an unrestricted view context, the view stream lane on both legs, native save and open dialogs in the desktop host, and the desktop Browser page, sequenced in `2026-10-27-sede-browser-plan`. Hypotheses that may change within the constraints: field and command names, the screencast's size cap, JPEG quality and frame rate, the framing of download and upload chunks, the worker view channel's endpoint namespace, the page-observer hook through which the browser session exposes popups, downloads, file choosers, dialogs and the provider's login pages to the screencast, how the person interrupts an assisted login step, and the icon.

Deferred: watching a sync live, and copying text out of the page, which would need script evaluation.

Accepted 2026-10-27 on the user's choice, in this session, of "stream our Chromium's page into a panel" and "implement 1)", on the user's ruling of 2026-10-27 that the browser is free use with no restriction or limit, and on session sharing through the same custody.

## Rationale

The screencast keeps the browser where custody and operation ownership already live. The window gains pixels and an input channel, never a cookie, a remote document or a debugging endpoint. That is the only shape that satisfies "same session as the CLI and TUI" and "nothing remote in the webview" together: a webview would need its own cookie jar, and shipping storage state anywhere breaks the custody rule. Seeding from custody and publishing back through the deferred writes reuses the one publication path, so the panel and the syncs agree without a second loader. The digest precondition keeps the panel from overwriting a newer acquisition. Holding the lock only around acquisition and publication keeps syncs usable while a view is open.

The view is a browser the person uses, so it carries no usage limits: a person's browsing is not something Cadrumo restricts or can enforce. The live-write guard binds what Cadrumo itself sends, and Cadrumo sends nothing in the view, so the guard's guarantee for automated flows and agent tools is untouched. What stays bound is who may see and drive the view: the attach token, same-peer check and unbinding on session retirement tie the lane to the exact session that started it, as the runtime binds every other act, and credit keeps video from blocking replies.

## Consequences

- Good: the person can use the Sede, or any site, inside Cadrumo as in any browser, log in by hand with any provider including Cl@ve Permanente, and a login there is reused by every CLI, TUI and desktop sync at once.
- Good: downloads and uploads use the native dialogs and keep their bytes outside Cadrumo custody unless the person imports them.
- Cost: what the person submits, signs or presents in the panel is the person's own act through Cadrumo's session. Cadrumo does not record it as local filing state or a captured observation; a later live read or receipt capture is the path into Cadrumo's records.
- Cost: a new runtime protocol lane, a new frame kind and a long-lived interactive operation class to maintain and test on every platform. Python and WebView copies of frames cannot be wiped.
- Reconsider if CDP screencast proves too slow at panel sizes, or if any Cadrumo-initiated request would need to run in the view's context.
