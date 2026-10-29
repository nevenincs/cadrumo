---
tags:
  - '#audit'
  - '#desktop-aeat-sync'
date: '2026-10-29'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:f8111c10f2072bbd958ba2de4c4baac97a1d7863b17cced37f7309bbef6bed80'
related:
  - "[[2026-10-29-desktop-aeat-sync-plan]]"
  - "[[2026-10-29-desktop-aeat-sync-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace desktop-aeat-sync with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `desktop-aeat-sync` audit: `desktop AEAT sync integrated review`

## Scope

Review of plan Step P07.S20 (2026-10-29): the integrated behaviour of commits `1c5e603d90` to `218afd038b` on `feature/tui` (backend `live.sync.status` and the four contract changes, host `native/desktop/src-tauri/src/shell/aeat_sync/`, frontend `components/aeatSync/`, ports, scenarios, census entries and locales) against the accepted desktop AEAT sync ADR and the records it amends or names. Reading was partitioned by layer; the host run model and outcome table were read in full.

Verification coverage: reused the ledger evidence (pytest aeat_sync 107/43/152 and focused contract tests, `just check-operation-contract-manifest`, `just check-style`, `just check-format`, `lint-imports` 30/30 contracts, `desktop-host-unit-test` aeat_sync filter and `just check-rust`, `npm run check`, Playwright aeat-sync 26 and the 69-test census set, `dev.locales status --check`, `desktop-frontend-generated`). Open gaps recorded in the ledger stand: `just check-types` red only in another session's `dev/docs` files, `just check-import-boundaries` reported unavailable because the tree changed mid-run. No additional checks were run: every finding below is a source-level defect, not a coverage gap. P07.S21 (attended live check) remains open.

Verdict: REVISION REQUIRED (one high finding).

## Findings

### session-ended-overrides-unknown | high | an ended session that may have kept something is resumed automatically instead of staying unknown

`native/desktop/src-tauri/src/shell/aeat_sync/outcome.rs:72` returns `Failed(SessionEnded)` before the `effect != "none"` check at `outcome.rs:75`, so a session-ended refusal whose receipt reports `updated`, `partial` or `unknown` is paused and then re-run by `Run::resume` (`run.rs:407-420`, `mod.rs:826`). The comment's premise, "an ended session refuses before anything is kept", does not hold: `live.filed-capture.bulk` raises the session-ended refusal per declaration inside its loop (`src/cadrumo/application/live/filed_data_capture.py:299`) after earlier declarations of the same year may have persisted, and the IVA history capture does the same (`iva_remote_state.py:299,355`). This contradicts the ADR constraint that outcome `unknown` is never retried automatically and that resume never re-runs an unknown item. The test `tests.rs:565` locks the wrong mapping in. Fix: map a session-ended refusal to `SessionEnded` only when `effect == "none"`; otherwise `Unknown` (person-acknowledged retry), and change the test row accordingly.

### identity-unknown-verdict-counts-as-brought | medium | a verify check that got no answer reads as brought and keeps the area current

`outcome.rs:105` treats verdict `unknown` as `Brought`, and the backend dates the identity area from every verify observation regardless of verdict (`src/cadrumo/application/aeat_sync/status_operation.py:193`). `IdentityCheckVerdict.UNKNOWN` means no answer was obtained (`src/cadrumo/core/identity_check_verdict.py:28`), so an outage refreshes "up to date" for 90 days. Fix: exclude unknown-verdict observations from `identity_checked_at` and settle the host item as failed (unavailable) on an unknown verdict.

Resolution (backend, 2026-10-29): `load_aeat_sync_status` no longer dates the identity area from a verify observation whose verdict is `unknown`; an area holding only such checks reads never brought. Covered through the real reader by `test_an_identity_check_that_got_no_answer_does_not_date_the_area` and its only-unknown companion. The host half (settling the item as failed on an unknown verdict) remains with the host worker.

### results-unknown-retry-dead-end | medium | the results view offers a retry for an unknown area that the host always refuses

`native/desktop/frontend/src/components/aeatSync/Results.tsx:292-303` calls `retry(result.area)` with no warning, and the results port sends no `acknowledged_unknown` (`src/shell/tauriHost.ts:169-171`). The host correctly refuses (`run.rs:469-475`), so nothing unsafe happens, but the button can never succeed from this view. Fix: route it through the same warn-then-acknowledge path the progress view uses (`AeatSyncProgress.tsx:90-131`).

### dry-run-and-selection-residue | medium | the host still admits a dry run and year/form selection that owner rulings removed, and the ADR still describes them

`mod.rs:58-60,90-95,372-375`, `run.rs:29-33`, and `src/shell/aeat_sync.ts:57-60` keep `dry_run`, `years` and `forms`; the window always sends `dry_run: false` and no selection (`AeatSyncPage.tsx:152`). The governing ADR still states a sign-in step, a selection with dry run and `aeat_sync_start (selection: areas, years, optional forms, dry run)` (`.vault/adr/2026-10-29-desktop-aeat-sync-adr.md` Implementation, Host and Run model paragraphs), and the sync-control-surface amendment still names the desktop dry run. Fix: remove the dead dry-run path from host and port, and amend the ADR (and the amended records) to the owner rulings recorded only in the ledger notes.

### en-locale-lines-uncommitted | medium | the source locale's session-ended and browser lines exist only in the working tree

`HEAD:src/cadrumo/locales/en/cli.yml` has no `session_ended` key while es, ca and hu do (`es/cli.yml:646`); the en browser line in `en/adapters.yml` is likewise uncommitted (ledger notes S06, S17). The committed tree therefore misses source-locale strings for this feature. Fix: commit those hunks by pathspec once the shared file's foreign hunks are settled.

### window-rederives-area-outcome | medium | the window computes each area's worst outcome and the borrador year range itself

`src/shell/aeatSyncRun.ts:83-95` re-implements the host's `outcome::worst` (`outcome.rs:186`) because the run snapshot serves only item states; `BorradorImport.tsx:14-21` hard-codes six filing years ending last calendar year, a support-year rule the backend owns (`status` already serves year lists). Fix: serve the area outcome in `AreaView` and the borrador years from `live.sync.status`.

### host-serial-and-reuse-gaps | medium | the borrador import and notification read skip the profile serial lock, and the notification read duplicates the views read

`aeat_sync_borrador_import` (`native/desktop/src-tauri/src/shell/aeat_sync/mod.rs:1167-1184`) submits a mutating import without `host.serial()`, which every other profile operation, including this module's own captures (`mod.rs:235`), takes. `aeat_sync_notifications` (`mod.rs:1113-1137`) re-implements `ProfileHost::notifications` (`user_profile/views.rs:328-353`) without its serial lock, `still_held` check or read limit. `aeat_sync_observe`/`unobserve` (`mod.rs:737-778`) copy the profile observe loop. Fix: take the serial lock for the import, and extend the canonical views read (or a shared helper) to return the rows rather than copying it.

### concurrent-start-can-orphan-a-driver | medium | two overlapping starts can replace a held run without ending its driver

`aeat_sync_start` (`mod.rs:697-708`) checks for an active run, releases the lock, then overwrites `held` without calling `Held::end` on what was there. Two starts racing on the multi-threaded runtime can leave the first driver task running unowned, submitting captures beside the second, against the one-item-at-a-time model the ADR's acquisition-lock hypothesis relies on. Fix: check and replace under one lock acquisition and end any replaced `Held`.

### progress-event-refinement-missing | low | per-year progress is not refined by the operation's observation events

The ADR's run model promises refinement within a year by the observation event cursor; `RelayDriver::capture` (`mod.rs:228-271`) follows only the terminal projection and `ItemView` has no progress field. Either implement or amend the ADR.

### status-result-and-test-gaps | low | smaller backend observations

`live.sync.status` declares `permitted_effects ["none","unknown"]` while its executor is a pure read; `CadrumoError` is outside `_STORE_READ_FAILURES` (`status_operation.py:75`) so one failing store fails the whole read instead of one area; a contested (differing) row can carry `receipt_confirmed` (`workspace_reader.py:925,943`); `test_status_operation.py:299-304` recomputes the expected year list with the implementation's expression; `test_status.py:254-255` compares a value with itself; only `OSError` store failures are tested.

Resolution (backend, 2026-10-29): `live.sync.status` is now an ephemeral no-effect read (shared `EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES`, `permitted_effects ["none"]`, manifest regenerated), a `CadrumoError` from one store marks only that area unavailable, and a differing filed row can no longer carry a confirmed receipt (reader and `AeatSyncFiledRowV1` validator). The year-list test now reads the registry declaration instead of recomputing the implementation expression, the self-comparison in `test_status.py` asserts the exact refusal per state, and failures other than `OSError` are tested.

### frontend-duplication | low | small duplicated helpers in the window

`OUTCOME_ICONS` is defined twice (`Results.tsx:23-28`, `AeatSyncProgress.tsx:24-29`); `AREA_ORDER` (`Results.tsx:30-37`) repeats `AEAT_SYNC_AREAS`; `areas_run_in_the_fixed_order` (`tests.rs:114-118`) compares `Area::ORDER` with its own sort; `FailedPart.form` is always `None` (`mod.rs:1037`); `aeatSyncDay` (`src/shell/aeatSync.ts:86-102`) duplicates `shared/dateFormats.ts`; locale keys `differs.amount` and `differs.date` are unused. Several Playwright zero-call assertions (`aeat-sync.spec.ts:210-404`) are not polled, and the borrador year expectation (`aeat-sync.spec.ts:536`) mirrors the implementation.

### confirmed-sound | low | areas checked and found consistent with the decisions

Closed admitted list including `auth.local-read`, checked against the manifest with read kinds asserting no record-changing effect; no submission definition admitted. Browser readiness comes only from the setup engine row (`setup/mod.rs` `browser_row`). Stop takes effect between items, pause and resume skip unknown items, reattach and discard on identity change (`mod.rs:183-194`, `user_profile.rs` close). No logging in the host module; leak test covers status, results and progress replies. Local record, AEAT observation and confirmed receipt stay three fields from backend row to `FiledResults.tsx:57-83`; a draft alone makes no row. Notification rows carry no ids and the Sede action opens at its start page. Census reuses the existing session and band.

## Recommendations

- Reopen P03.S10 and P03.S11 for `session-ended-overrides-unknown` before P07.S21.
- Fix `identity-unknown-verdict-counts-as-brought`, `results-unknown-retry-dead-end`, `host-serial-and-reuse-gaps`, `concurrent-start-can-orphan-a-driver` and `window-rederives-area-outcome` within the approved P02/P03/P04 Steps.
- Amend `2026-10-29-desktop-aeat-sync-adr` and `2026-08-08-sync-control-surface-adr` to the owner rulings (no sign-in or selection screen, no dry run) and decide whether event-cursor progress stays in scope.

## Resolutions

- `session-ended-overrides-unknown`: resolved in fb5296ee4f. `outcome.rs` checks the effect first, so a session-ended refusal pauses only with effect `none`; `updated`, `partial` and `unknown` settle the item `unknown`, which resume never re-runs. The table test covers each effect and a run test proves the partly kept item is not re-read. P03.S10 and P03.S11 re-closed.
- `concurrent-start-can-orphan-a-driver`: resolved in fb5296ee4f. `SyncHost::begin` checks and replaces the held run under one lock, keeps a run that still moves or whose driver still follows it, and ends any run it replaces; tested.
- `identity-unknown-verdict-counts-as-brought`: host side resolved in fb5296ee4f (an unknown verdict settles failed, unavailable); the backend side is in feb59b85b1.
- `host-serial-and-reuse-gaps`: resolved in fb5296ee4f. The Borrador import takes the serial lock; the notification rows come from `ProfileHost::notifications_read`, shared with the profile view; the profile, census and AEAT sync cues share one `Cue` holder.
- `dry-run-and-selection-residue`: resolved in fb5296ee4f (host, contract, ports, fixtures) and 6540349d1e (desktop AEAT sync ADR and the sync control surface amendment restated to the owner rulings).
- `window-rederives-area-outcome`: resolved in fb5296ee4f. The host serves each area's outcome in the progress snapshot and the Borrador years (the served supported filing years, else the six years ending last calendar year) in status and results; the window renders them.
- `results-unknown-retry-dead-end`: resolved in fb5296ee4f. The results view warns through the shared warning and sends the acknowledgement; a scenario covers it.
- `progress-event-refinement-missing`: not implemented; the ADR now states progress is item-level and events are not read (6540349d1e).
- `frontend-duplication`: resolved in fb5296ee4f (one icons module, served area order, shared day formatter, `FailedPart.form` removed, polled zero-call assertions, Borrador year expectation from served data, explicit area-order test). The unused locale keys are removed in the working tree but not committed: the shared catalogue and key files carry other sessions' hunks.

## Re-review (2026-10-29)

Scope: the fixes in `feb59b85b1` (backend), `fb5296ee4f` (host and frontend), `6540349d1e` (ADRs) and `b131aca3f4` (audit and ledger), with their interactions. Unchanged behaviour was not reviewed again. Verification coverage: reused the ledger evidence (`npm run check`, Playwright aeat-sync 27, the host and backend runs recorded for the reopened Steps). No additional checks were run, because the findings below are source-level and the fixture ports cannot exercise them. P07.S21 (attended live check) remains open.

Confirmed resolved: `concurrent-start-can-orphan-a-driver` for two starts (`SyncHost::begin` checks and replaces under one hold), `identity-unknown-verdict-counts-as-brought` (backend reader and `outcome.rs:107`), `host-serial-and-reuse-gaps`, `dry-run-and-selection-residue` (no `dry_run`, `years` or `forms` left in host, contract, ports or fixtures apart from refusal tests), `window-rederives-area-outcome` (`AreaView.outcome` and served `borrador_years`), `progress-event-refinement-missing` (the ADR states item-level progress), `frontend-duplication` (code part), and `status-result-and-test-gaps`. `live.sync.status` now shares `EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES` with the profile views, and the manifest entry matches (`permitted_effects ["none"]`, `ephemeral`). No host code or test assumes an unknown or journaled status read. The desktop AEAT sync ADR and the sync control surface amendment now state no sign-in step, no selection screen and no dry run.

### session-ended-never-pauses-a-writing-capture | high | for VAT and filed declarations, an ended session no longer pauses the run, and every later item turns unknown

The fix in `outcome.rs:73-78` pauses only on a session-ended refusal with effect `none`. But a capture that may write reports `unknown` before it reads anything. `prepare_provider_capture` calls `track_capture_session(..., may_write=True)` (`src/cadrumo/application/live/live_operation_execution.py:118-127,148`), which emits `OperationEffect.UNKNOWN` before any AEAT request, and the supervisor copies `snapshot.effect` into the refused receipt (`src/cadrumo/application/operations/_supervisor_execution.py:417`). `live.filed-capture.bulk` (`filed_bulk_capture_operation.py:182`, `may_write` is always true now that the dry run is gone) and `live.iva-wallet.history-capture` (`iva_wallet_history_capture_operation.py:140`) therefore can never settle session-ended with effect `none`. Their session-ended refusals all become `Unknown` (correctly, for the item), but `Run::settle` (`run.rs:354`) pauses only on `Failed(SessionEnded)`. The run keeps submitting the remaining filed years against the ended session, and each one also settles `unknown`. In those areas the run never pauses or offers sign-in and resume, which is what ADR Interruptions describes. Every remaining year then needs a person-acknowledged retry, even when nothing was kept. The verify, notifications and discovery captures still pause, because their effect stays `none` until a write. The run test at `tests.rs:384` feeds `Step::Vat` a `Failed(SessionEnded)` that the real VAT capture cannot produce. Fix: separate "pause the run" from "the item's outcome". A session-ended refusal pauses the run whatever its effect, and the item settles `unknown` when the effect is not `none`, so resume still never re-runs it. Add a run test with an unknown session-ended item followed by waiting items.

### acknowledged-retry-key-never-reaches-the-host | medium | the acknowledged retry is sent as `acknowledged_unknown`, which Tauri 2 does not bind, so the results-view fix is still a dead end

`results-unknown-retry-dead-end` is not resolved in the real app. Both ports send `acknowledged_unknown: acknowledgedUnknown` (`native/desktop/frontend/src/shell/tauriHost.ts:174` for results and `:190` for progress; the progress one predates the fix). `aeat_sync_retry` (`native/desktop/src-tauri/src/shell/aeat_sync/mod.rs:811-818`) is a plain `#[tauri::command]` with no `rename_all`, so Tauri 2 binds the camelCase key `acknowledgedUnknown`. The rest of the file follows that convention (`taxValues`, `grantId` at `tauriHost.ts:534-536`). The `Option<bool>` parameter silently reads `None`, and `Run::retry` refuses with `unknown` every time. As a result, no unknown item can be retried from the progress or results view. The Playwright scenarios use fixture ports and cannot see this. Together with the finding above, the unknown items it multiplies cannot be recovered from the page. Fix: send `acknowledgedUnknown` in both ports, and add a host-side check of the command argument names (or one live or Tauri test of the retry command).

### retry-drive-can-abort-a-fresh-run | medium | a retry racing a start can abort the new run's in-flight capture and leave its item running forever

`SyncHost::drive` (`mod.rs:186-205`) attaches to whichever `Held` carries the identity, not to the run the caller claimed. If a retry or resume obtains the old run's `Arc` (`session`), and then a start replaces that run (`begin` replaces a `Done` or `Stopped` run, `mod.rs:166-184`) and spawns its driver, the retry's `claim()` on the old run succeeds. Its `drive` then aborts the new run's task (`current.task.take()...abort()`) and spawns a fresh loop over the new run. The aborted item stays `Running` and is never settled, which leaves a capture that may have been submitted outside the unknown discipline. The new start path did not introduce this race, but the fix's claim that a held run cannot be left without its driver does not cover it. Fix: pass the claimed run's `Arc` to `drive`, and attach only when `Arc::ptr_eq` matches the held run.

### en-locale-lines-still-uncommitted | medium | `en-locale-lines-uncommitted` remains open

`HEAD:src/cadrumo/locales/en/cli.yml` still has no `session_ended` key (working tree `en/cli.yml:600`), and the en `browser.errors.not_available` line in `en/adapters.yml` is still the old wording at HEAD while es is committed (`ba5a53ba05`). The removal of the unused `differs.*` keys is also uncommitted. Nothing in the resolutions addresses this. Commit the hunks by pathspec, or record who owns the shared file's remaining hunks.

### status-store-catch-swallows-other-refusals | low | a broad `CadrumoError` catch can turn an authority or custody refusal into one area unavailable

`_STORE_READ_FAILURES` now includes `CadrumoError` (`src/cadrumo/application/aeat_sync/status_operation.py:77`), and only `ProfileAccessRefusedError` is re-raised first (`:148`). A store reader's `RefusalError` or `AutomationCustodyError` would read as "unavailable" for that area instead of refusing the read. The live captures re-raise all three (`filed_data_capture.py:296`). Re-raise the same refusal set before the store catch.

### begin-keeps-a-just-finished-run | low | a start in the instant between the last settle and the driver's release is silently ignored

`Run::active` now counts `driving` (`run.rs:260-266`), so a start that lands after the last item settles but before `next()` releases the driver keeps the finished run, and the window reattaches to it with nothing new running. The window is narrow and the person can start again, but `aeat_sync_start` answers `Ok` without a run.

### re-review-verdict | high | REVISION REQUIRED

One high finding (`session-ended-never-pauses-a-writing-capture`) reopens P03.S10 and P03.S11 before P07.S21. The acknowledged-retry key, the retry-drive race and the en locale lines are medium. Fix them within the approved P03, P04 and P05 Steps.

## Re-review resolutions

- `session-ended-never-pauses-a-writing-capture`: resolved in 9366afc6df. Pausing is now separate from the item's outcome. `outcome::session_ended` and the driver's `unsucceeded` mark every session-ended terminal projection, and `Run::settle` pauses on it whatever the effect. With effect `none` the item settles failed (session ended) and resume reads it again. With any other effect it settles `unknown`, resume never re-runs it, and the run carries on with the next item not done. The table-driven run test feeds each admitted capture its real effect order through the relay driver's own reader: the verify checks, notifications and discovery report `none` before a write; the VAT history and filed declaration captures report `unknown` before they read (`may_write`); and after a partial write the effect is `unknown`, `partial` or `updated`. P03.S10 and P03.S11 re-closed.
- `acknowledged-retry-key-never-reaches-the-host`: resolved in 9366afc6df. Both ports and the typed contract now send `acknowledgedUnknown`. `the_window_sends_each_command_the_argument_names_tauri_binds` parses every `aeat_sync_*` command signature in `mod.rs` and its `args` in `ipc/contract.ts`, and fails on any name other than Tauri's camelCase binding or on a required argument that the contract marks optional. `npm run check` type-checks the ports against that contract.
- `retry-drive-can-abort-a-fresh-run`: resolved in 9366afc6df. `begin` answers the run it claimed. `drive`/`follow` attach only when `Arc::ptr_eq` matches the held run; otherwise they release the claimed run and never abort the held run's task. The race is tested with a gated driver.
- `begin-keeps-a-just-finished-run`: resolved in 9366afc6df. `Run::active` counts only a paused run or one with an item waiting or running, so a start arriving after the last settle holds a fresh run. This is tested.
- `status-store-catch-swallows-other-refusals`: resolved in b7e9cb1949. `PersistenceDegradationError` replaces `CadrumoError` in the store catch, and access, custody and transport refusals are re-raised first. The status composition translates adapter `StorageError` into that degradation at the seam. Tests cover propagation of `RefusalError`, `AutomationCustodyError` and `InternalInvariantError`.
- `en-locale-lines-still-uncommitted`: not addressed in this pass. It remains open.

## Third review (2026-10-29)

Scope: only the behaviour changed in `9366afc6df` (host and frontend), `b7e9cb1949` (backend status refusals) and `6f4064e229` (audit and ledger), with their interactions. Verification coverage: reused the ledger evidence for S10, S11, S15 and S04 (`desktop-host-unit-test aeat_sync 37` and `user_profile 30`, `just check-rust`, `npm run check`, `playwright aeat-sync 27`, `pytest aeat_sync status 143`, style, format, types and `lint-imports`, all pass). No additional checks were run, because none of the gaps below can be closed by a focused run. P07.S21 (attended live check) remains open.

Confirmed resolved:

- `session-ended-never-pauses-a-writing-capture`: `outcome::session_ended` (`outcome.rs:89`) and `unsucceeded` (`mod.rs:227`) carry the flag separately from the outcome. `Run::settle` pauses on it whatever the effect (`run.rs:345`). `resume` re-queues only `Failed(SessionEnded)` and not-started items, so an unknown item is never re-run and the run continues after it. A relay follow error still settles `unknown` without pausing, which is correct. The table test drives every relay step (verify, notifications, VAT, discover, filed) with its effect order through `unsucceeded`.
- `acknowledged-retry-key-never-reaches-the-host`: both ports and `HostCommands` send `acknowledgedUnknown`. The argument-name test parses every `#[tauri::command]` in `mod.rs` (all `aeat_sync_*` commands live there; none uses `rename_all`), excludes injected `State`/`WebviewWindow` parameters, and requires the contract's key sets to equal Tauri's camelCase binding. `progress` and `updates` channels, `subscription`, `profile`, `area`, `item`, `request`, `file`, `year` and `language` all bind correctly. `tauriHost.ts` is held to the contract by the typed `hostCall`, so `npm run check` covers the call sites.
- `retry-drive-can-abort-a-fresh-run`: `begin` answers the claimed run, and `follow` attaches only on `Arc::ptr_eq`, releasing a superseded claim and never aborting the held run's task (`mod.rs:206-224`). The replaced loop has already released its claim, so leaving its handle unaborted is safe.
- `begin-keeps-a-just-finished-run`: `Run::active` (`run.rs:264`) counts a paused run, or a running or stopping run with an item waiting or running. A discovery's year items are inserted under the same lock as its settle, so a start cannot replace a run between a discovery and its years. Replacing a finished run aborts a driver with nothing in flight.
- `status-store-catch-swallows-other-refusals`: access, custody and transport refusals are re-raised before the store catch (`status_operation.py:167`), and other registered errors propagate. `_latest_identity_check` is a behaviour-preserving extraction of the `feb59b85b1` fix.
- Sweep check: `6f4064e229` touches only the audit and the ledger. The plan file was last changed in `218afd038b`, and `status_operation.py` changes only in `b7e9cb1949`, which contains only this fix. No foreign edits were swept in. An uncommitted refactor of `workspace.py` validators (another session's work, behaviour-preserving) is in the working tree and was not committed by these changes.

### en-locale-lines-still-uncommitted | medium | carried open: the en `session_ended` line and the browser wording are still only in the working tree

This is unchanged from the previous round. The session-ended pause now runs for every relay capture, so the committed product depends on the uncommitted `en/cli.yml` `session_ended` key even more than before.

### status-storage-translation-too-broad | low | every adapter `StorageError` becomes an unavailable area, including a sealed profile session and integrity failures

`degrade_storage_failure` (`src/cadrumo/entrypoints/aeat_sync_status_composition.py:20-31`) translates every `StorageError` into `PersistenceDegradationError`. That includes `SessionExpiredError` (a sealed profile session, an authority condition), `PathContainmentError`, `SecureObjectRowIdentityError` and `BlobIntegrityError`. A session sealed during the read therefore shows every area as unavailable instead of refusing the read, and an integrity failure looks like a transient outage. This is the same class of problem as `status-store-catch-swallows-other-refusals`, moved to the seam. Fix: translate only I/O-class storage failures, and let session-expiry and integrity errors propagate.

### census-session-end-does-not-pause | low | a census item whose AEAT session ended settles failed (other) and the run does not pause there

The commit says every admitted capture pauses on an ended session, but the census step does not go through `unsucceeded`. `census_outcome` maps the census host's `failed` state to `Failed(Reason::Other)` (`native/desktop/src-tauri/src/shell/aeat_sync/mod.rs:410`), and `censo.rs:159-163` reports every effect-`none` refusal as `failed` without its `refusal_ref`. The run then moves on, and pauses only at the next relay item. Resume does not re-read the census, so the person has to retry that area by hand. The impact is small because census is first and the next item pauses. Fix: let the census snapshot carry the session-ended refusal so it settles `Failed(SessionEnded)`, or record that the census is out of scope for the pause.

### third-review-verdict | medium | PASS

No critical or high findings. The four fixes under review hold, and their interactions (resume, retry, start replacement, status refusal propagation) are consistent. One medium (`en-locale-lines-still-uncommitted`, carried) and two lows remain recorded for the approved P02, P03 and P05 Steps. Verification coverage is the reused ledger evidence listed above. P07.S21 is still pending.

### Third review resolutions

- `status-storage-translation-too-broad`: resolved. `degrade_storage_failure` now translates only a repository failure, a missing blob and an unusable keychain into the persistence degradation. A sealed profile session and every integrity failure (containment, row identity, blob digest, decryption, envelope) propagate with their own meaning. Tests cover each propagating class, the missing blob, and a session sealed through the composed ports' real repository path.
- `census-session-end-does-not-pause`: resolved. The census snapshot carries `session_ended`, read from the observed projection by `outcome::session_ended` (no second classification). `census_outcome` settles an effect-none ended session as `Failed(SessionEnded)` and pauses the run; an ended session whose effect may have kept something settles `unknown`, pauses, and is not re-run on resume. Host tests cover the snapshot flag, the settlement and the run-level pause and resume.
