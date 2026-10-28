---
tags:
  - '#audit'
  - '#sede-browser'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:97da38e01bbba29c499229dba44b8a7e0c50a4f6a31c9c1a4914d574da862e23'
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

### view-state-non-https | high | On a non-https page the toolbar and the external open keep the previous page

`src/cadrumo/adapters/outbound/aeat/browser/sede_view.py:123-158` returns no state for any page that is not https, and `ViewState` itself refuses non-https origins (`src/cadrumo_client/contracts/view_stream.py:203-210`), so nothing is sent. `native/desktop/src-tauri/src/shell/sede_view.rs:940-943` clears the held address only when a state arrives. After a move from the Sede to an `http:`, `data:` or error page, the toolbar still shows the earlier https origin and path. That spoofs the address the person trusts, and "Open in external browser" opens the earlier page, not the current one. Fix: always emit a state on main-frame navigation; for a page that cannot be stated, send a typed unstated or insecure marker with no address, so the host clears its address and the toolbar says so.

### window-close-publication | high | Closing the window loses the close-time publication to the session ending

`native/desktop/src-tauri/src/app.rs:277-279` calls `SedeViewHost::close` (`sede_view.rs:1271-1277`), which only queues `view.close` and returns. `sign_in.stop` then drops the person connection at once (`shell/sign_in/mod.rs:411-415`), which retires the session, unbinds the view and cancels the operation. The worker skips publication once a cancel is requested (`src/cadrumo/application/live/sede_view_operation.py:464`), and a publication already running hits the retired session at the effect guard. This breaks the ruling that `view.close` publishes, and contradicts the comment "while the person's session is still held". Fix: in `close`, wait a bounded time for the view to reach `Phase::Ended` (its settled receipt) before the profile and sign-in hosts close.

### browser-page-lifetime | medium | Leaving the Browser page ends the view, where the ADR keeps it running

`native/desktop/frontend/src/App.tsx:3096-3097` mounts `BrowserPage` only while it is the shown page, and `src/components/browser/useSedeView.ts:102-109` closes the view on unmount. Each page switch therefore publishes, closes Chromium and loses the page state and history. The ADR's Window constraint says "Leaving the page keeps the view running without frames". Fix: keep the page mounted while it is hidden, or amend the ADR.

### worker-input-drop | medium | The worker silently drops person input past 64 queued items

`src/cadrumo_runtime/host/worker_view_stream.py:89-95` and `:392-394` discard input once 64 items are waiting, for example while `adapter.input` or an assisted-login cancel is in progress. A dropped key-up leaves a key or modifier held down, and dropped text is lost. This bound conflicts with the free-use ruling, and the host already bounds its queue with a refusal (`sede_view/upstream.rs:16-18`). Fix: never drop key, text or button events; coalesce only pointer moves, and apply backpressure upstream.

### download-cleanup-race | medium | A download being streamed at close can outlive the browser's cleanup

`src/cadrumo/adapters/outbound/aeat/browser/sede_view.py:278-286` cancels `_deliver`, but its `asyncio.to_thread` worker (`:435-441`) keeps the transient file open inside `send_download`. That worker waits until the sink ends (`worker_view_stream.py:243-244`), and the sink is closed only after `browser.close()` (`sede_view_operation.py:398-399`, `:469-470`). On Windows, `download.delete()` and Playwright's removal of its artifacts directory can then fail while the handle is open, leaving the private bytes on disk. Fix: cancel the sender in the sink and join the thread before the download is discarded and the browser closes.

### signed-out-page-verification | medium | Every changed AEAT page load while signed out runs a full provider verification

`sede_view_operation.py:304-318` publishes whenever the captured digest differs from the baseline. Ordinary cookie churn changes that digest on most loads. Each publication takes the acquisition lock and launches the provider's own Chromium to probe AEAT (`sessions.py:1545-1568`), which also makes concurrent syncs defer. Fix: run the check only when the provider's session cookies appear or change, keyed on the provider's declared cookie names.

### dead-offer-contract | medium | The forced-external offer codes survive on every leg but are never produced

`DOWNLOAD_OFFERED` and `FILE_CHOOSER_OFFERED`, with `ViewOffer` (`src/cadrumo_client/contracts/view_stream.py:113-124`, `:226-245`), the host's offer table (`sede_view.rs:517-536`, `:956-961`, `:1441`) and the frontend's `offerId` remain from the restricted design; no worker code emits them. Fix: delete them across the contract, the vectors (regenerated by `view_stream_vector_source`), Rust and the frontend in one change.

### clave-manual-publication | medium | A Cl@ve Movil profile without its contraste cannot publish a manual login

`sessions.py:1536-1544` runs `_prepare_clave_auth`, whose `_require_clave_credentials` (`sessions.py:864-870`) demands the app-route contraste even though a manual login never uses it. The capture ends `verification-failed`. Fix: for view captures, require only the identity that the alignment needs.

### coverage-certificate-adr | medium | The plan's related list omits a governing decision

`2026-07-16-protected-browser-certificate-auth-adr` governs the view's certificate provisioning (`sessions.py:1420-1452`) but is not in the plan's `related:`. No constraint is broken. Fix: add the link with `vaultspec-core vault link add`.

### aeat-click-target | low | The AEAT rail click shows the open view's current page, not the Sede

`App.tsx:749-757` and `:2907-2909` only reveal the page. Fix: send the `home` verb when a view is already open.

### upload-cancel-scope | low | Cancelling one upload drops every pending chooser

`sede_view.py:410-413` ignores `transfer_id`. Fix: map transfers to their chooser.

### adr-wording-drift | low | The ADR still says view.state carries the origin and path only, and that moves are coalesced in the worker

The S16 address field and the worker's lack of coalescing (`view_input.py:15-16`; the host coalesces at `upstream.rs:36-44`) differ from that wording. Fix: amend the ADR text.

### test-support-import | low | A runtime test imports another package's test support

`src/cadrumo_runtime/host/tests/test_view_stream_integration.py:38-45` imports from `cadrumo.adapters.outbound.aeat.auth.tests`. Fix: use a typed fixture interface at the orchestration seam.

## Recommendations

- Reopen P02.S05 and P05.S12 for view-login-identity, P02.S07 and P03.S16 for view-state-non-https, and P03.S08 for window-close-publication; re-review those changes before P06.S14.
- A follow-on decision may be needed on how the view presents insecure or unstateable pages in the toolbar, and on whether leaving the page ends the view (amend `2026-10-27-sede-browser-adr`).
- Verification reused from the ledger: S01/S15/S16 codec and vector checks, S02/S07 relay and operation tests, S03/S08/S16 `just check-rust` and every non-installer CTest target, S09-S11 frontend checks and scenarios, S12 auth suites, S13 cross-leg integration. Rerun here: `lint-imports` (30 kept, 0 broken) and `view_stream_vector_source --check` (pass). Gaps: the bundle gate was not run because it depends on the MSI target; P06.S14 is pending with the orchestrator and the operator.
