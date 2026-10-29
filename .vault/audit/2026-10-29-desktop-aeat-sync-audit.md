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

### frontend-duplication | low | small duplicated helpers in the window

`OUTCOME_ICONS` is defined twice (`Results.tsx:23-28`, `AeatSyncProgress.tsx:24-29`); `AREA_ORDER` (`Results.tsx:30-37`) repeats `AEAT_SYNC_AREAS`; `areas_run_in_the_fixed_order` (`tests.rs:114-118`) compares `Area::ORDER` with its own sort; `FailedPart.form` is always `None` (`mod.rs:1037`); `aeatSyncDay` (`src/shell/aeatSync.ts:86-102`) duplicates `shared/dateFormats.ts`; locale keys `differs.amount` and `differs.date` are unused. Several Playwright zero-call assertions (`aeat-sync.spec.ts:210-404`) are not polled, and the borrador year expectation (`aeat-sync.spec.ts:536`) mirrors the implementation.

### confirmed-sound | low | areas checked and found consistent with the decisions

Closed admitted list including `auth.local-read`, checked against the manifest with read kinds asserting no record-changing effect; no submission definition admitted. Browser readiness comes only from the setup engine row (`setup/mod.rs` `browser_row`). Stop takes effect between items, pause and resume skip unknown items, reattach and discard on identity change (`mod.rs:183-194`, `user_profile.rs` close). No logging in the host module; leak test covers status, results and progress replies. Local record, AEAT observation and confirmed receipt stay three fields from backend row to `FiledResults.tsx:57-83`; a draft alone makes no row. Notification rows carry no ids and the Sede action opens at its start page. Census reuses the existing session and band.

## Recommendations

- Reopen P03.S10 and P03.S11 for `session-ended-overrides-unknown` before P07.S21.
- Fix `identity-unknown-verdict-counts-as-brought`, `results-unknown-retry-dead-end`, `host-serial-and-reuse-gaps`, `concurrent-start-can-orphan-a-driver` and `window-rederives-area-outcome` within the approved P02/P03/P04 Steps.
- Amend `2026-10-29-desktop-aeat-sync-adr` and `2026-08-08-sync-control-surface-adr` to the owner rulings (no sign-in or selection screen, no dry run) and decide whether event-cursor progress stays in scope.
