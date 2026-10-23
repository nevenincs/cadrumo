---
tags:
  - '#audit'
  - '#ledger-tui-doors'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:26346bbdaaa5b82c7d02935d0e3e31e1906360b18764270c2e5e71bda2f758d1'
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

## Recommendations

- Event loop: move every blocking session check in a runtime door off the loop, and add thread-recording tests for each door that does not go through `run_operation`.
- Navigation during a write: the Records workspace refuses area and tool changes while its body reports a write in flight. Test each write flow.
- Timeout or ambiguous write: after submission, report a typed outcome-unknown refusal carrying the operation id and the observed effect. Screens show it as unknown and re-read before offering a retry, and the B4 tests cover the deadline and unknown-effect cases.
- P04.S13: link the secure-storage hardening ADR to the plan, and amend it to record the stricter fail-closed refusal.
- Bulk classify: send every reviewed row and let the operation report applied and skipped rows.
- Stale records: a follow-on decision should settle whether `ledger.update`, `ledger.invoice.update`, `ledger.invoice.remove` and the reset preview carry revision or digest preconditions.
- Paging: `invoice.list`, the register lists, `evidence.query`, `rule.list` and `consent.list` take no paging fields. Paging them needs a decision on those request contracts.
