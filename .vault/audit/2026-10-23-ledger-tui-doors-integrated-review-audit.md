---
tags:
  - '#audit'
  - '#ledger-tui-doors'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:f2d2578b5a5057441f4b3a66b7b1a5d4063d1ff5b950e72f73dc968fa4ff4ada'
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

### settlement | low | Correction: a typed denial at start stays unknown

The second re-review's start-denial finding rests on a wrong premise. The runtime runs `worker.start` (`operation_projection.py:116`), which makes RUNNING durable and creates the settlement task, before `host.authorize(release)` (`profile_connection_operations.py:320`) can raise a typed `ProfileAccessRefusedError`. A typed denial in reply to `operation_start` can therefore sit on top of a running write, so reporting it as unknown is correct. `OperationController.start` also never sees an `AccessRefusal`: `frontend_operation_client.py:81-99` converts it first. No change is made.

### settlement | medium | Third re-review: a saved own-account write whose follow-up read fails is worded as not saved

`own_accounts.py:423-447` sends the write and the register re-read in one `try`. A re-read refused while the session is live shows "The change was refused or could not be saved." and re-enables Confirm with the request staged; a probe confirmed it (`list`, `add`, `list`). Register uniqueness refused the repeat, so nothing was duplicated. `registers_presentation.py:461-464` shows the right shape: unstage and word the write once it returns, then re-read separately.

### settlement | medium | Third re-review: a categorisation review whose modal loses observation after Apply closes silently

`categorisation_review.py:166-174` with `operations/modal.py:315-327,432-442`. When observation is refused or access is lost after Apply, the modal dismisses with `None` and `_review_settled` clears the status, so a started and possibly applied review shows nothing and can be reviewed again. This path bypasses `failure_after_submission`.

### settlement | medium | Third re-review: recomposing on session loss can wipe the unknown-outcome message

`app_navigation.py:375-399`, `app.py:378,440-443`. A closed transport or the lapse timer recomposes without asking the destination, and `AccountRecomposeRequiredV1` carries no operation id, so the session-lost unknown wording may only flash before bootstrap. Signing in re-reads the records, so there is no double write; what is lost is which operation was unknown. Not reproduced.

### settlement | low | Third re-review: record and transaction edits check the exact unknown type

`record_views.py:568-581,589-592` and `transaction_views.py:262-269` use `isinstance(error, OperationOutcomeUnknownError)`, so a session-lost unknown outcome leaves Save, Cancel or Remove enabled over the old baseline.

### frontend-behaviour | low | Third re-review: an older records load can re-enable evidence Add over stale rows

`evidence_records.py:53-56,81-84,263`. A records load started before an unknown Add that lands afterwards releases Add over rows read before the write.

### frontend-behaviour | low | Third re-review: the asset write hold is released by inspecting any asset

`actividad_asset.py:190-191`. Any successful inspection releases the hold, and a typed not-found for the held asset does not.

### quality | low | Third re-review: the evidence records load fails the app on an ordinary refusal

`evidence_records.py:58-64` catches only `AccountSessionExpiredError`; a `RefusalError` from `list_records` (`runtime_evidence.py:157-158`) fails the worker with `exit_on_error` on.

### settlement | low | S26 follow-on: no typed not-found for an activity asset

The asset write hold is now bound to the asset each action names and released only by a successful inspect of that asset. Releasing it on a not-found for that asset would prove a held create did not land, but `inspect` raises a plain `ActividadAssetValidationError` (`application/actividad_asset/operations.py:85`), rebuilt without its text at `activity_asset_contracts.py:170`. Releasing on it would mean matching message text, so an unknown create that did not land stays held until the operator leaves the screen. A typed not-found refusal is a change to the inspect contract.

### settlement | low | S26 follow-on: operation modal callers outside Records ignore a dismissal without an outcome

`aeat_sync/screens.py:510`, `modelo/workbench/screen_operation.py:210`, `operations/settled_submission.py:51` and `profile/manager_client.py:440` (runtime) treat a `None` dismissal as nothing, and `setup/screen.py:283` re-reads without saying the outcome is unknown. `operations/run_screen.py:485` already words it as unobserved with the operation id. These are outside the Records plan.

### frontend-behaviour | medium | Fourth re-review: a manual split during the re-read after an unknown review drops the re-read's continuation

`refresh_then` keeps a single continuation (`controller.py:679`). On `LedgerSplitScreen` an unknown review calls `reread_then` (`categorisation_review.py:223-226`); the manual split is not gated by `review_awaits_reread` (`categorisation_split.py:153-154`), and its success path calls `refresh_then(self.after_refresh)` (`categorisation_common.py:365`), replacing `landed`. Ask then stays refused for the life of the screen, and `refuse("")` (`categorisation_common.py:327`) erases the unknown review's operation id. A probe confirmed it; nothing is written twice.

### frontend-behaviour | low | Fourth re-review: a failed re-read withholds the write with no retry and hides the Home guidance

`_reread_after_unknown_review` (`categorisation_review.py:228-233`) overwrites the `refresh_failed_unknown` line, and Ask only repeats the unknown wording without starting another re-read. Evidence Add has the same shape after a failed records load (`evidence_records.py:68-70`).

### copy | low | Fourth re-review: write_outcome_unknown is never cleared

A later saved write whose re-read fails is worded as possibly unsaved (`evidence_records.py:309-311`). The read counters allow a safe reset: record `_refreshes_started` when the unknown outcome arrives and clear the flag once `_refreshes_returned` exceeds it.

### settlement | low | Fourth re-review: an own-account write with an unknown outcome keeps its secrets and is offered again over the old register

`own_accounts.py:435-447` unstages without clearing the account-number inputs (unlike `:454`) and without re-reading the register (unlike `registers_presentation.py:445-451`), so update, close or designate can be resent against an outdated register. `_submit` also no longer clears `_busy` on a non-Cadrumo exception.

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
- The third re-review passes S22. The own-accounts follow-up read, the modal `None` dismissal and the four lows are in-scope corrections for P03.S26. Whether the recompose outcome carries pending unknown operations is a follow-on decision on the recompose contract.
- The fourth re-review passes S26. Its medium and three lows are in-scope corrections for P03.S27.
