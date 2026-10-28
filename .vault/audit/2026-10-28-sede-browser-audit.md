---
tags:
  - '#audit'
  - '#sede-browser'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:261e2526ac97dff59d9b2f623969d08822220e76c007591ee8e83738e4aa80fc'
related:
  - "[[2026-10-27-sede-browser-plan]]"
  - "[[2026-10-27-sede-browser-adr]]"
---
# `sede-browser` audit: `Sede browser plan-close integrated review`

## Scope

Plan-close integrated review of `2026-10-27-sede-browser-plan` at HEAD `0ebde50b27` on `feature/tui`, Steps P01.S01 to P06.S13 and P01.S15, P03.S16; P06.S14 (attended live check) is open and runs after this review. Governing: `2026-10-27-sede-browser-adr`, the 2026-10-27 amendments of `2026-10-03-aeat-live-write-guard-adr`, `2026-10-04-application-sign-in-adr` and `2026-10-04-desktop-shell-adr`, `2026-06-04-live-auth-decomposition-adr` and `2026-07-16-protected-browser-certificate-auth-adr`, plus the user rulings of free use, kept security binding, one shared session and the AEAT rail button. The 27 uncommitted files in the worktree (components and provisioning) are outside this feature and were not reviewed. Traced: open, attach, stream, input, navigate, download and upload, close and publish; sign-out mid-view; manual login with empty custody then reuse by `ensure_authenticated_aeat_session`; external open of the exact address. Verdict: REVISION REQUIRED.

## Findings

### view-login-identity | high | A login made in the view is published under the profile's identity without observing who signed in

`src/cadrumo/application/auth/sessions.py:1567` and `:1744` treat the identity returned by `adopt_view_capture` as verified, but every provider writes that identity from configuration, not from the session: `src/cadrumo/adapters/outbound/aeat/auth/authenticator.py:421-431` (certificate NIF), `clave_movil.py:345-380` and `clave_permanente.py:217-244` (configured DNI/NIE); the probe at `authenticator.py:718-758` checks only that a protected page loads. A person who signs in by hand as another taxpayer, or as a representative, has that session stored as this profile's, and every later CLI or TUI sync reads the other taxpayer's data into this profile, so the ADR's required active-profile identity alignment is tautological. Fix: have each provider's capture proof read the authenticated NIF from an AEAT page and compare it with the profile before anything is staged for publication, returning `verification-failed` on a mismatch or when the NIF cannot be read.

Resolved: b56b862b74

### view-state-non-https | high | On a non-https page the toolbar and the external open keep the previous page

`src/cadrumo/adapters/outbound/aeat/browser/sede_view.py:123-158` returns no state for any page that is not https, and `ViewState` itself refuses non-https origins (`src/cadrumo_client/contracts/view_stream.py:203-210`), so nothing is sent. `native/desktop/src-tauri/src/shell/sede_view.rs:940-943` clears the held address only when a state arrives. After a move from the Sede to an `http:`, `data:` or error page, the toolbar still shows the earlier https origin and path. That spoofs the address the person trusts, and "Open in external browser" opens the earlier page, not the current one. Fix: always emit a state on main-frame navigation; for a page that cannot be stated, send a typed unstated or insecure marker with no address, so the host clears its address and the toolbar says so.

Resolved: 7de262810f (with b454e17d2e)

### window-close-publication | high | Closing the window loses the close-time publication to the session ending

`native/desktop/src-tauri/src/app.rs:277-279` calls `SedeViewHost::close` (`sede_view.rs:1271-1277`), which only queues `view.close` and returns. `sign_in.stop` then drops the person connection at once (`shell/sign_in/mod.rs:411-415`), which retires the session, unbinds the view and cancels the operation. The worker skips publication once a cancel is requested (`src/cadrumo/application/live/sede_view_operation.py:464`), and a publication already running hits the retired session at the effect guard. This breaks the ruling that `view.close` publishes, and contradicts the comment "while the person's session is still held". Fix: in `close`, wait a bounded time for the view to reach `Phase::Ended` (its settled receipt) before the profile and sign-in hosts close.

Resolved: c4d3de56f0

### browser-page-lifetime | medium | Leaving the Browser page ends the view, where the ADR keeps it running

`native/desktop/frontend/src/App.tsx:3096-3097` mounts `BrowserPage` only while it is the shown page, and `src/components/browser/useSedeView.ts:102-109` closes the view on unmount. Each page switch therefore publishes, closes Chromium and loses the page state and history. The ADR's Window constraint says "Leaving the page keeps the view running without frames". Fix: keep the page mounted while it is hidden, or amend the ADR.

Resolved: dc6ab7705a (ADR amended; leaving the page does not close the view).

Resolved: 4726994819

### worker-input-drop | medium | The worker silently drops person input past 64 queued items

`src/cadrumo_runtime/host/worker_view_stream.py:89-95` and `:392-394` discard input once 64 items are waiting, for example while `adapter.input` or an assisted-login cancel is in progress. A dropped key-up leaves a key or modifier held down, and dropped text is lost. This bound conflicts with the free-use ruling, and the host already bounds its queue with a refusal (`sede_view/upstream.rs:16-18`). Fix: never drop key, text or button events; coalesce only pointer moves, and apply backpressure upstream.

Resolved: 7e52953901

### download-cleanup-race | medium | A download being streamed at close can outlive the browser's cleanup

`src/cadrumo/adapters/outbound/aeat/browser/sede_view.py:278-286` cancels `_deliver`, but its `asyncio.to_thread` worker (`:435-441`) keeps the transient file open inside `send_download`. That worker waits until the sink ends (`worker_view_stream.py:243-244`), and the sink is closed only after `browser.close()` (`sede_view_operation.py:398-399`, `:469-470`). On Windows, `download.delete()` and Playwright's removal of its artifacts directory can then fail while the handle is open, leaving the private bytes on disk. Fix: cancel the sender in the sink and join the thread before the download is discarded and the browser closes.

Resolved: 632d04acbf

### signed-out-page-verification | medium | Every changed AEAT page load while signed out runs a full provider verification

`sede_view_operation.py:304-318` publishes whenever the captured digest differs from the baseline. Ordinary cookie churn changes that digest on most loads. Each publication takes the acquisition lock and launches the provider's own Chromium to probe AEAT (`sessions.py:1545-1568`), which also makes concurrent syncs defer. Fix: run the check only when the provider's session cookies appear or change, keyed on the provider's declared cookie names.

Resolved: 1d41de0fbf

### dead-offer-contract | medium | The forced-external offer codes survive on every leg but are never produced

`DOWNLOAD_OFFERED` and `FILE_CHOOSER_OFFERED`, with `ViewOffer` (`src/cadrumo_client/contracts/view_stream.py:113-124`, `:226-245`), the host's offer table (`sede_view.rs:517-536`, `:956-961`, `:1441`) and the frontend's `offerId` remain from the restricted design; no worker code emits them. Fix: delete them across the contract, the vectors (regenerated by `view_stream_vector_source`), Rust and the frontend in one change.

Resolved: 3dab8ab998

### clave-manual-publication | medium | A Cl@ve Movil profile without its contraste cannot publish a manual login

`sessions.py:1536-1544` runs `_prepare_clave_auth`, whose `_require_clave_credentials` (`sessions.py:864-870`) demands the app-route contraste even though a manual login never uses it. The capture ends `verification-failed`. Fix: for view captures, require only the identity that the alignment needs.

Resolved: e3da9ab6ee

### coverage-certificate-adr | medium | The plan's related list omits a governing decision

`2026-07-16-protected-browser-certificate-auth-adr` governs the view's certificate provisioning (`sessions.py:1420-1452`) but is not in the plan's `related:`. No constraint is broken. Fix: add the link with `vaultspec-core vault link add`.

Resolved: ec97843317

### aeat-click-target | low | The AEAT rail click shows the open view's current page, not the Sede

`App.tsx:749-757` and `:2907-2909` only reveal the page. Fix: send the `home` verb when a view is already open.

Resolved: 7de262810f

### upload-cancel-scope | low | Cancelling one upload drops every pending chooser

`sede_view.py:410-413` ignores `transfer_id`. Fix: map transfers to their chooser.

Resolved: 53e2cf1850

### adr-wording-drift | low | The ADR still says view.state carries the origin and path only, and that moves are coalesced in the worker

The S16 address field and the worker's lack of coalescing (`view_input.py:15-16`; the host coalesces at `upstream.rs:36-44`) differ from that wording. Fix: amend the ADR text.

Resolved: dc6ab7705a

### test-support-import | low | A runtime test imports another package's test support

`src/cadrumo_runtime/host/tests/test_view_stream_integration.py:38-45` imports from `cadrumo.adapters.outbound.aeat.auth.tests`. Fix: use a typed fixture interface at the orchestration seam.

Resolved: d26178dd66

## Recommendations

- Reopen P02.S05 and P05.S12 for view-login-identity, P02.S07 and P03.S16 for view-state-non-https, and P03.S08 for window-close-publication; re-review those changes before P06.S14.
- A follow-on decision may be needed on how the view presents insecure or unstateable pages in the toolbar, and on whether leaving the page ends the view (amend `2026-10-27-sede-browser-adr`).
- Verification reused from the ledger: S01/S15/S16 codec and vector checks, S02/S07 relay and operation tests, S03/S08/S16 `just check-rust` and every non-installer CTest target, S09-S11 frontend checks and scenarios, S12 auth suites, S13 cross-leg integration. Rerun here: `lint-imports` (30 kept, 0 broken) and `view_stream_vector_source --check` (pass). Gaps: the bundle gate was not run because it depends on the MSI target; P06.S14 is pending with the orchestrator and the operator.

## Re-review after the plan-close fixes

Re-review at HEAD `12b15b83af` on `feature/tui`, clean worktree, of the changed behaviour of the resolving commits b56b862b74, e3da9ab6ee, 1d41de0fbf, 558e8e7919, b454e17d2e, 3dab8ab998, 7e52953901, 632d04acbf, c4d3de56f0, 4726994819, 53e2cf1850, 39f7fe1ade, 8fda44a544, d26178dd66, the follow-ups e454b09756, 17e7ba5ec3, 6ae8acfe87 and 2acc174685, and the state-marker and AEAT-click hunks of 7de262810f. Every prior finding is fixed on the legs it touches. The identity read runs in the provider's own Chromium context seeded from the capture, through the censal reader's guarded request and landing refusals; it never touches the person's page. A mismatch, an unreadable consulta and a NIF-less consulta all return inside `defer_writes`, whose exit discards the staged writes, so nothing is published or deleted. A mismatch reaches the window as the `identity_mismatch` notice and close outcome on the contract, vectors, Rust documents, host and frontend. The input pacing cannot deadlock against credit, because the executor never waits on anything the reader delivers, and `close` and `_stop` wake a held reader. The download cleanup deletes the transient file on every path: completed, refused, failed, cancelled by the window, and cut short by the view's close. The offer codes are gone from every leg. The hidden-window close joins repeated requests and counts its deadline once. No usage restriction has returned: the 1024-item input pacing, the 90 s shutdown bound and the refused-jar memo limit nothing the person may do. Verdict: PASS. P06.S14 remains pending.

### hidden-view-frames | medium | The hidden Browser page keeps the full screencast flowing

`native/desktop/frontend/src/components/browser/useSedeView.ts:62-71` credits every image, and `BrowserSurface.tsx:122-127` keeps it aside while the page is hidden. The worker therefore keeps encoding JPEG frames and relaying them over both legs and the shell channel for as long as the page is put aside, which is continuous on animated pages. The ADR's Window constraint says "Leaving the Browser page keeps the view running without frames". Fix: grant no credit while the page is hidden. The producer then holds only its newest pending image, and granting credit again on show delivers it, so the put-aside image path is no longer needed.

### identity-probe-representado | medium | The identity probe asks the consulta for the expected NIF as `nifRepresentado`

`src/cadrumo/adapters/outbound/aeat/auth/view_capture_identity.py:38` reads the consulta through `censal_datos_url` (`src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py:482`), which requests `nifRepresentado=<expected NIF>`. A person who signs in as a representative holding an apoderamiento for the profile's taxpayer may be served that taxpayer's consulta. The check would then pass and publish a representative's session, while every other Sede reader, none of which passes `nifRepresentado`, reads the signed-in identity's own data. The refusal relies on AEAT answering with its representation dialog; nothing in the repository grounds that. Fix: read the signed-in identity from a surface that does not take the expected NIF as input. Alternatively, ground the dialog answer with a specimen in P06.S14 and record it.

### paced-input-host-deadline | low | Paced input can end the view through the runtime's 5 s worker write

`src/cadrumo_runtime/host/worker_view_stream.py:424-436` holds the reader once 1024 inputs wait. The runtime's `_write_worker` (`src/cadrumo_runtime/host/view_stream_relay.py:506`) then blocks, and once the pipe buffer is full and the stall exceeds `_FRAME_SECONDS`, it ends the view `FAILED`. A page hung for several seconds under sustained input therefore loses the view instead of being paced. The new relay test stalls for only 1 s. Fix: let the upstream worker write wait while the worker leg is alive, bounded by liveness rather than a per-frame deadline, and test a stall longer than 5 s.

### signed-out-jar-rotation | low | The refused-jar memo counts every cookie value in the context

`src/cadrumo/application/live/sede_view_operation.py:207-229` digests every cookie's domain, path, name and value, including other sites' cookies and any rotating load-balancer or WAF cookie on the AEAT hosts. If AEAT rotates such a value per response, each signed-out AEAT load still launches a provider Chromium under the acquisition lock, which the original finding meant to stop. Fix: measure it during P06.S14. If it recurs, key the memo on the cookies of the AEAT and Cl@ve authentication hosts.

### relaunch-during-hidden-close | low | A relaunch while the hidden window publishes fails after 10 s

`native/desktop/src-tauri/src/shell/single_instance/mod.rs:42` waits `PATIENCE` (10 s) for the lock, while the hidden close may wait up to `relay::SETTLE_LIMIT` (90 s, `native/desktop/src-tauri/src/shell/sede_view.rs:1341`). The close-time publication now launches a provider Chromium and reads the consulta, so it can plausibly exceed 10 s, and a person who closes and reopens at once gets a launch `TimedOut`. This conforms to the ADR's "within its usual patience". Fix: when the holder has signalled that it is closing, let the second launch wait up to the settle limit. That is a follow-on amendment of `2026-10-27-sede-browser-adr`.

### Re-review recommendations

- None of these findings reopens a Step. Address hidden-view-frames under P04.S09 and paced-input-host-deadline under P01.S02. Ground identity-probe-representado and signed-out-jar-rotation in P06.S14 before it closes.
- Follow-on decision to name: how long a second launch waits for a closing window (amend `2026-10-27-sede-browser-adr`).

### Re-review verification

Rerun here: `uv run --no-sync pytest -m "not aeat_live"` over `test_view_stream_documents.py`, `test_sede_view_page.py`, `test_view_input.py`, `test_sede_view_operation.py`, `test_view_session_custody.py`, `test_view_sign_in.py`, `test_view_stream_relay.py` and `test_view_stream_integration.py`: 258 passed (run log under `var/storage/development/.logs/test-runs/2026-10-28/20261028T090906.674161Z-pytest-70600-4b920f39`). `lint-imports --no-cache`: 30 kept, 0 broken. Reused from the ledger for the native and frontend legs: S08 `just check-rust` and `desktop-host-unit-test` pass after the hidden-window close, S09 `npm run check` and the sede-browser Playwright scenarios pass after the page-lifetime change, and S12 `desktop-host-unit-test` and the Playwright scenarios pass after the identity notice. Native builds and CTest were not rerun because a concurrent session owns `just build-native Debug bundle`, and the bundle gate stays unrun because of its MSI dependency. Pending: the attended live check P06.S14, owned by the orchestrator and the operator. It is the only place where the AEAT answers behind identity-probe-representado and signed-out-jar-rotation can be observed.
