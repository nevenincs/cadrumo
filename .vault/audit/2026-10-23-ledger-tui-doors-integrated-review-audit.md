---
tags:
  - '#audit'
  - '#ledger-tui-doors'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:111249310fff4c0282255e998abd686e0a71ea556d6d7dbdfee6cf9413affb08'
related:
  - "[[2026-10-22-ledger-tui-doors-plan]]"
---

# `ledger-tui-doors` audit: `integrated review`

## Scope

Final integrated review of `2026-10-22-ledger-tui-doors-plan`, from `0df71b71b6` to `786fca7c34`, covering P01.S01, P02.S02 to S06, P03.S07 and P04.S09 to S19. It was reviewed against the navigation-join, ledger latency budget and authenticated stored-reads decisions and the swarm base brief. Gate and suite execution for P03.S08 ran separately. The findings rest on code reading at the cited lines.

## Findings

### event-loop | high | Two runtime doors still check their session over blocking IPC on the event loop

`src/cadrumo_runtime/host/frontend/tui/runtime_ledger_categorisation.py:496,515,526` (suggestion review submit and read_result) and `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_invoices.py:71` (import preview) call `require_binding()` directly. That reaches `client.status()` (`runtime_account_session.py:70`), and the screens await those doors from async workers on the loop (`categorisation_review.py:136,143,174,190`, `invoices_import.py:234,239`). Every key freezes for a runtime round trip. `test_categorisation_event_loop.py:75-76` leaves these doors unguarded. Since `d84d3a639a`, all five domains await their doors on the loop, so the no-blocking guarantee rests on each runtime door doing its own blocking work off the loop.

### settlement | high | Choosing an area or tool during a write abandons it and loses its outcome

`controller.py:714-722` (`_open_tool`) and `controller.py:743-761` (`handle_navigation_selection`) swap the workspace body without checking for a write in flight; only Back is guarded. Unmounting cancels the screen's workers, so the awaited door is cancelled after submission and the operator never sees the outcome of, for example, a reset, merge, evidence batch or invoice import. A retry may then duplicate or contradict the write.

### settlement | high | A timed-out or ambiguous write is reported as refused or not saved

`runtime_profile_session.py:115,128-134` waits at most 120 s and then raises `RefusalError(DEADLINE_EXCEEDED)` while the operation may still be settling. Lines 169-176 raise for a non-SUCCEEDED receipt without its effect, so UNKNOWN or PARTIAL is lost. Only the entries export door works around this (`runtime_ledger_entries.py:449-533`). Write screens then show the generic "refused or could not be saved" copy, for example `entries_reset.py:235-238`.

### coverage | medium | The plan does not link the secure-storage ADR that governs P04.S13

P04.S13 made a session lapse during a secure-object batch read refuse the whole read (`secure_objects.py:704-708`). `2026-08-22-secure-storage-performance-hardening-adr` requires performance work to preserve refusal semantics; the change fails closed but is not recorded there.

### frontend-behaviour | medium | Bulk classify silently drops rows whose classification already matches

`categorisation_bulk.py:293-295` keeps only rows whose classification differs from the target, so a category or business percentage the operator entered is not applied to matching rows. A page where every row already matches is refused as having nothing to change. Which rows to skip is application behaviour that `ledger.classify.bulk` already reports.

### s19 | low | The especial-regime partition reads vocabulary at today's date, not the row's date

`iva_ledger.py:921-939` resolves input classifications at `today_madrid()`, while the per-row admission check in `_iva_transaction.py:314-324` uses the ledger date. The two diverge once fact 0116 gains a second dated variant; today it has one.

### records | low | Update and remove doors guard against stale records with a racy re-read

`runtime_ledger_records.py:187-189,195,220,267-268` re-reads and compares before writing. A change that lands between the re-read and the write goes undetected.

### quality | low | Each register and invoice door builds its own session, each with a blocking check

There are separate session constructions in `runtime_ledger_registers.py:140,493-495`, `runtime_ledger_invoices.py:62,115`, `runtime_ledger_entries.py:561,642` and `runtime_ledger_records.py:131,331`. Each makes a synchronous status round trip when the ledger factory is built (`runtime_workbench.py:395-404`).

### confirmation | low | Register writes confirm inline rather than through the shared confirmation flow

`registers_presentation.py:275-283,392-400` uses a Review then Confirm button pair. None of these operations deletes anything.

### settlement | high | Re-review: app-level navigation still swaps out the Records body during a write

Re-review of P03.S20 to S25 (`0f10a06111` to `802d691424`). The S21 guard covers only routes the workspace handles itself. `app_navigation.py:96` (`navigate_to`) and `:319`, `:332-341` (`_replace_destination`, `_swap_destination`) never ask the body. Ctrl+P destination, search and operation commands (`search.py:304,325,339`, `operations/palette.py:68`), F4 Profile and F2 Language (`app.py:780,792-794`), a desktop page request (`app.py:428`), and change user or sign out all unmount the body mid-write. A probe confirmed it in the real `CadrumoTuiApp`. `ActivityAssetScreen` has no in-flight guard.

### settlement | high | Re-review: failures after the operation started other than timeouts still read as refusals

`runtime_profile_session.py:163-179` converts only four transport refusal codes. These still surface as plain refusals although the change may be saved:
- an observation refused while running (`operation_controller.py:634-635`, `observation.py:112-113,127-128`);
- a refused or malformed result read after a SUCCEEDED or UPDATED receipt;
- a door admit or settle correlation failure after a committed receipt (`runtime_evidence.py:293-310`).

All three were confirmed by probe. When the submit reply is lost, `controller` is None and the operation stays CREATED and never started, so that path is correctly a refusal.

### event-loop | high | Re-review: the evidence extract and confirm doors still check the session on the event loop

`runtime_evidence.py:208` (`extract`) and `:235` (`confirm`) call `require_binding()` directly in async methods awaited from loop workers (`evidence_records.py:142-148,184,216`). A thread-recording probe saw one of three session reads on the loop thread, and no thread test covers this door.

### settlement | medium | Re-review: a dropped connection after submission reads as an expired session

A failed exchange closes the transport (`operation_transport.py:70-72`). The recheck at `runtime_profile_session.py:164-167` then gets `AccountSessionUnavailableError`, and `session_expired_with_receipt` reports "sign in again". The operation id and the unknown effect stay in a context the screens never render, so the CONNECTION_CLOSED case is unreachable.

### frontend-behaviour | low | Re-review: review exclusion and evidence add re-offer the write without re-reading

`review.py:332-341` and `evidence_records.py:261-270` handle an unknown outcome without re-reading, so the same write can be offered again at once.

### copy | low | Re-review: a read that times out says the change may have been saved

`run_operation` raises outcome-unknown for read-only definitions too, and `review.py:206-209` shows the write wording. It should do so only when the definition permits an effect beyond NONE.

### s24 | low | Re-review: choosing an evidence draft resets the cursor to the top

`evidence.py:320-323` repaints with `table.clear(columns=True)`, which resets the cursor and scroll.

### s25 | low | Re-review: the body walk does not recurse into subpackages

`test_every_body_answers_an_area_choice.py:106-122` uses `pkgutil.iter_modules`. A body in a future `ledger/` subpackage would escape the walk.

### settlement | high | Second re-review: activity-asset writes check their result after run_operation returns

`runtime_actividad_asset.py:205-207,235-237,285-301,325-331`. `create`, `correct` and `record_claim` declare an UPDATED effect and raise a plain `INVALID_FRAME` refusal when the result lacks `history`, lacks the asset's revision, or names another claim. Those checks run after `_call` (`:139-147`) returns, so `failure_after_submission` never judges them. The screen shows `refused` (`actividad_asset.py:171-174`) with every button live, and a repeated `correct` appends a duplicate revision. The unknown branch (`actividad_asset.py:167-170`) also re-offers the write without re-reading.

### settlement | medium | Second re-review: a session lost with an unknown outcome is still worded as not saved

The session-lost outcome errors subclass the session errors, so catch order is safe and private views are dropped. But the session branches print a definite failure: `evidence_records.py:220,260`, `invoice_entry.py:602`, `entries_add.py:353`, `registers_presentation.py:442`, `categorisation_review.py:149,207`, `actividad_asset.py:165`. In `review.py:345-355` they fall to the generic branch, where `failed_write_status` (`controller.py:652`) recognises only `OperationOutcomeUnknownError`; queue rows and `pending_exclusion` are kept until the root recomposes. The pre-submit binding check blocks a same-session retry, so there is no double apply.

### settlement | medium | Second re-review: the categorisation result read checks the session outside the shared judgement

`runtime_ledger_categorisation.py:534-540`. `read_result` runs after a SUCCEEDED receipt that may be UPDATED, but its `require_binding()` and identity check sit before the `try` at `:544`. A session lost in that gap reads "Not done." (`categorisation_review.py:204-208`) for a saved change.

### settlement | low | Second re-review: a typed runtime refusal at start is reported as unknown

`OperationController.start` maps an `AccessRefusal` reply to `INVALID_FRAME` (`operation_controller.py:504-505`), so a typed denial looks like a malformed reply. The supervisor refuses before entering the executor (`_supervisor_execution.py:146-239`), so a typed denial proves nothing ran. Reporting unknown is the safe direction, only less precise.

### frontend-behaviour | low | Second re-review: evidence add is offered again before the re-read lands, or when it fails

`evidence_records.py:266-270,289-292`. `refresh_then` calls `then()` after a failed `_refresh` (`controller.py:680-689`), and `_reoffer_add` re-enables Add while `_show_records` is still reading.

### navigation | low | Second re-review: a cleared review can leave the evidence body in flight

`evidence_records.py:207-213`. If the review is cleared before the `_confirm` worker runs, `_confirm` returns without clearing `reading`, so `in_flight` stays true and, after S21, Back, the account keys and quit stay refused until the session lapses. Not reproduced.

## Recommendations

- Event loop: move every blocking session check in a runtime door off the loop, and add thread-recording tests for each door that does not go through `run_operation`.
- Navigation during a write: the Records workspace refuses area and tool changes while its body reports a write in flight. Test each write flow.
- Timeout or ambiguous write: after submission, report a typed outcome-unknown refusal carrying the operation id and the observed effect. Screens show it as unknown and re-read before offering a retry, and the B4 tests cover the deadline and unknown-effect cases.
- P04.S13: link the secure-storage hardening ADR to the plan, and amend it to record the stricter fail-closed refusal.
- Bulk classify: send every reviewed row and let the operation report applied and skipped rows.
- Stale records: a follow-on decision should settle whether `ledger.update`, `ledger.invoice.update`, `ledger.invoice.remove` and the reset preview carry revision or digest preconditions.
- Paging: `invoice.list`, the register lists, `evidence.query`, `rule.list` and `consent.list` take no paging fields. Paging them needs a decision on those request contracts.
- The P03.S20 to S22 re-review findings reopen those Steps. Every path after start, and every way of leaving a body, must go through one shared check rather than through per-scenario fixes.
- The second re-review passes S20 and S21 and reopens S22: activity-asset correlation must move into `settle`, session-lost unknown outcomes must read as unknown on every write screen, and the categorisation result read must be judged inside the shared check.
