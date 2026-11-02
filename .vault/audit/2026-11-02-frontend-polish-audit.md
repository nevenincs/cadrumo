---
tags:
  - '#audit'
  - '#frontend-polish'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:c62b8f7be1c4bd05f2c41e0ba60bc4da2cddf1d701a71010cebb402bb2331358'
related:
  - "[[2026-11-02-frontend-polish-plan]]"
---

# `frontend-polish` audit: `Frontend workflow coverage and hardening`

## Scope

Application-wide frontend hardening under the approved frontend-polish plan. Root implements; Terra performs read-only workflow discovery and Sol designs confirmed presentation gaps. This rolling record distinguishes static review from browser evidence. It is not yet a completed application-wide audit.

S08 static coverage: shared buttons, inputs, textarea, native select, field, calendar, combobox, suggestions; dialog, sheet, popover, dropdown menu, escape layers, reveal, tabs, radio, switch, toast, alert; table-view, data-grid header/row, keyboard/viewport/navigation/selection, checkbox, text-tip and segmented control; typed editor dispatch, EntryInput, TypedField, Date, Code, Notes, Percent, number reading, fieldCheck and editor props. Traced consumers include profile code suggestions, ledger classifications, invoices, documents, assets and grid cells. Remaining evidence: browser reproductions and fixes below, integrated consumers and performance measurement. Static coverage alone does not close S08.

S11 static workflow coverage: declarations list and creation targets; WorkspaceScreen and form/baseline loading; Form, Details/Todo, Check, Sources, History/corrections and Filing; staged edits, preflight, one stale-baseline renewal, apply, calculate/verify, local export, local filing records and justificante import. Reviewed useEditReview, form/session and filing/modelo contracts. Authority includes accepted desktop-modelo-workspace, modelo-editor-workbench-operator-layer and filing-chain-reconciliation decisions. No AEAT submission is implemented or inferred. Remaining evidence: settlement fixes, structured reconciliation details and integrated scenario checks.

## Findings

### shared-control-keyboard | medium | Highlight visibility and no-match Tab require repair

Static S08 findings: `native/desktop/frontend/src/components/ui/suggestions.tsx` changes active-descendant without revealing the active item in its scroll container. `components/ui/combobox.tsx` intercepts Tab before discovering that no selectable option exists. Reproduce with overflowing choices and no-match/disabled choices; repair under S18, preserving valid-choice behavior. Grid navigation also retains an active column after it disappears; reproduce column-hide focus before claiming a failure. Table collation uses the browser locale; this is a presentation candidate, not a proven breach of the ADR's date/number locale contract.

### modelo-uncertainty | high | Local uncertainty holds can disappear on navigation

Static S11 findings: `NewDeclarationDialog.tsx` resets its attempt when changing periods or reopening, before a successful read establishes current state. `FilingView.tsx` holds uncertainty only while mounted; changing workspace tabs clears that hold. Workspace lifetime alone does not cover leaving and reopening a declaration. Unknown operation settlement must not be inferred from an immediate reread. Successful writes also release busy state before awaited refresh and can leave stale actions available after refresh failure. Unknown writes omit the list's `onWritten` invalidation. S19/S20 must retain uncertainty at an appropriate existing in-memory lifetime, preserve backend authority, and verify delayed/failed recovery without automatic mutation retry.

### reconciliation-detail | medium | Returned differences and limitations are omitted

`FilingView.tsx` reduces a typed reconciliation result to matches plus an internal English narrative, dropping field differences and advisory context. S21 follows the Sol design: keep verdict/diffs/advisories in memory; summary plus visible semantic difference list, values labelled In Cadrumo/In imported document, missing strings displayed as missing rather than zero; preserve legal/source reference identifiers without inventing links. Always show advisory messages, with code/context in a details disclosure. Warning tone applies to limitations even when compared values match. Keep receipt status driven by the authoritative envelope. Do not render narrative identifiers, paths or digests. Backend advisory prose currently lacks translated variants; localize chrome without pretending messages are locale keys. Historical reconciliation reads are a separate future feature, not required by this repair.

### dock-landmark | medium | Full-window accessibility exposed a missing main landmark

Run `20261102T155752Z-48608` passed 54 of 56 ledger documents/read/setup cases; both setup accessibility cases failed landmark-one-main and region at the shell/dock controls. S22 adds a main role to the existing dock workspace container and a floating-pane assertion, pending the same light/dark audits and docking regressions. No layout or focus change is intended.

### verification-baseline | low | Broad checks have unrelated formatting failures

The current npm check passed TypeScript, ESLint, ledger contract checks and 34 unit tests, then failed Prettier on App.tsx, LedgerInspector.tsx, LedgerPage.tsx and ../scripts/frontend-build.mjs. Targeted S01 ESLint and Prettier passed. Preserve unrelated work; do not describe the full check as passing until formatting is resolved by its owner or in an authorized scoped correction.

### s01-review | low | Document and register lifecycle repair passes

PASS for S01. Reviewed identity-tagged reads, payload availability, held snapshot behavior, generation cleanup and direct-hook coverage. Ledger profile remounting remains the production account boundary; this repair does not claim a demonstrated cross-profile leak. Both new deferred-response cases pass, and the broader 56-case documents/setup suite passed all 54 behavior checks. Its two shell-landmark failures were isolated to S22 and subsequently passed after that semantic repair. TypeScript, scoped lint/format and existing unit/contract evidence apply. The initial source changes were captured by concurrent commit e6a39bc125; the S01 checkpoint adds final cleanup dependencies and harness timing corrections.

### s02-review | high | Interrupted refresh must resume after hiding

REVISION REQUIRED from Terra review of S02 after its first 13 passing cases: cancelling a refresh while hiding the mounted list could leave its cached list non-stale and its read phase stuck, skipping a new request on return. Root added interrupted-request tracking and a hide/show regression. This entry remains pending until the corrected focused run passes; original unmount/cache preservation cases are retained.

### s22-review | low | Main landmark restoration passes

PASS for S22 semantic scope: the existing dock container now supplies one main landmark without DOM reparenting, geometry or focus changes. Three focused browser cases pass: tab/split/float keyboard movement with preserved instance, and full-window Setup accessibility across light/dark themes. The test asserts a single visible main and that floating pane controls remain inside it. Targeted ESLint passed and the test was formatted. Broader app review remains open.

### s02-corrective-review | low | Interrupted refresh correction passes

PASS for corrected S02. Terra rereview confirms interrupted requests are retried while completed cache entries remain reusable; the completion guard runs before marking a request settled. Both final deferred-response tests pass, including same-mounted hide/show, workspace unmount with late success/failure, mounted write invalidation and no-write cache reuse. The earlier 11 UI declaration scenarios passed and their affected behavior is unchanged. Final TypeScript and scoped formatting pass; scoped ESLint passed. No new high/critical findings remain in this Step.

### s03-review | low | Provider settlement and cached status ordering pass

PASS for S03. Terra reviewed mutation guards across reader/host replacement and A-null-A return, plus accepted cached answers superseding older pending reads. Seven focused cases and seven existing provider UI cases pass (settings reopening, save/refusal secret handling, switches, sign-in completion, late account-change start, unavailable account). TypeScript and targeted ESLint pass; changed files formatted. The change suppresses obsolete UI updates; it does not cancel or reinterpret backend writes. Scenario evidence does not establish packaged-host behavior.

### s09-static-coverage | low | Account and profile review found no new concrete defect

Terra inspected userProfile state/readback, ProfileEditor, AeatAccessEditor, CreateProfile, ManageProfiles, SignIn, shell/signIn, AccountMenu, ProfileDialogs and profileInput. Covered loading/unavailable/signed-out/unknown creation/conflict/saved-unread/refusal; masked write-only fields, revision/digest drafts, focus restoration, navigation guards, password clearing, deletion acknowledgement and reobservation. No new correctness or privacy defect established. Existing verification seams are user-profile, profiles, manage-profiles and profile-views scenarios; S09 still needs applicable integrated evidence. Clearing corrected CreateProfile errors sooner is optional UX polish, not a proven contract defect.

### s12-static-coverage | medium | AEAT observation and Sede recovery need focused repairs

Terra traced overview, preflight, dependencies/access, assisted sign-in, host-owned progress queue, area results, comparisons, notifications and Borrador import; BrowserPage/Toolbar/Surface/Prompts/PageDialog, useSedeView and the typed Sede port. Accepted desktop-aeat-sync and sede-browser decisions preserve no-network status reads, host queue lifetime, explicit uncertain retry, person-driven browser actions and native upload/download authority. S23 addresses progress errors hidden both before any snapshot and after a retained clean done snapshot, without interpreting absent progress as permission for another update. S24 addresses page-dialog answers removed before confirmed enqueue even when native code restores the offer on queue refusal; download/chooser offers have different consumption semantics and must not inherit that fix. Resize records a sent size before acknowledgement and swallows rejection; retain acknowledged geometry and provide bounded recovery without replaying input. Input rejection is also swallowed, but its outcome needs precise host-code grounding before deciding warning/retry behavior. Existing test seams: aeat-sync and sede-browser, using fixtures only. Calendar coverage grouping is already verified, but S12 is not closed.

### s04-review | low | Agent observations and reading choices follow profile identity

PASS for S04. Terra reviewed first-render identity gates, continuous observation cleanup, subscription disposal and model choice attempt lifetime. Three direct lifecycle cases plus the existing document-reading model-picker case pass; five existing agent cases pass for lock/unlock, message streaming, unavailable runtime and catalog lane/model behavior. TypeScript and scoped ESLint pass; sources/tests formatted. The direct A-to-B switch is demonstrated in the scenario/hook harness, not claimed as the only real account transition. Existing same-profile choice-result ordering and revision-conflict rereads are preserved. No new high/critical findings in the scoped review.

### vault-verification | low | Scoped repair cleanup was interrupted

Read-only scoped vault checks reported only template annotations, stale index and body stamps. The broad scoped autofix applied annotation/stamp cleanup but continued consuming CPU without returning; root stopped that own process and rebuilt the feature index through its owning command. Do not treat the interrupted check as a pass; rerun bounded owning checks before final handoff.

### s05-s07-review | low | Complete matching evidence and stable invoice rows pass

PASS for S05/S07. The shared matching Chips view now renders every supplied chip with wrapping; the Turia fixture asserts number, date gap, counterparty and amount while retaining link accessibility and ambiguity semantics. Invoice grid rows are memoized by the already-memoized filtered/sorted invoice rows, preserving indexing and viewport dependencies on unrelated local updates. This avoids unnecessary row-array/index rebuilds; no measured latency claim is made. All 25 matching/invoice scenarios passed, including editing, sorting/filtering, uncertain writes and light/dark accessibility. TypeScript and scoped ESLint passed; changed files formatted. Root reviewed these narrow diffs against the Terra/Sol grounding.

### s04-checkpoint | low | Shared commit captured the implemented agent changes

Concurrent commit 3978e6c5e2 captured the root-implemented S04 source and tests before root staged its checkpoint. ecccd77d02 records the matching execution/review checkpoint. The passing evidence applies to those unchanged sources; no duplicate implementation was made.

## Recommendations

Finish the named repair Steps and append their actual verification and review verdicts here. Extend workflow inventories for S09-S15 and measured performance S16 before final S17 review. Unreviewed workflows remain open.
