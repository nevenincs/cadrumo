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

### s06-review | low | Saved-result reload failures and empty outcomes are explicit

PASS for S06. Sol designed the retained-result warning/local reload; Terra confirmed authority and partial-data preservation. Canonical locale batch updated en/es/ca/hu and desktop-frontend-chrome generation passed. TypeScript and targeted ESLint passed; sources/tests formatted. Thirty AEAT cases passed in the full run; four added language recovery cases initially failed because the test used visible retry text instead of the area-specific accessible name. After correcting that selector, all four passed. Failed/unknown empty rows suppress confirmed-absence messages; successful empty retains them; partial rows survive failure; local reload does not issue another remote retry. Adjacent pre-existing unknown retry handling is separately tracked in S25 and remains open.

### aeat-retry-uncertainty | high | An unknown retry can leave old failed-result controls active

Terra identified that remote retry returning unknown sets trouble but retains an old failed result; failed-part controls can then retry with acknowledgedUnknown=false, especially when the local reread also fails. S25 must preserve the unknown gate until explicit acknowledgement or an authoritative settled result; use the existing UnknownWarning and do not automatically replay the remote action.

### s25-corrective-review | low | Exact retry acknowledgement scopes and serialization pass

PASS for corrected S25. Terra traced aeat_sync_retry through the host run mutex: its unknown refusal requests acknowledgement before mutating selected unknown items. It does not establish that this attempted retry started and lost its response. Results now retains exact part/all acknowledgement scopes, preserves them across unrelated successes and partial acknowledgements, and blocks overlapping requests synchronously. The host remains authoritative when the Results component remounts; fresh-start replacement is a separate path and is not claimed fixed. Six focused browser regressions pass, including failed local reload, unrelated years, whole-area uncertainty and pending overlap. TypeScript, targeted ESLint and formatting pass. Corrective Terra review found no remaining concrete defect in this same-run path.

### s18-review | low | Suggestion visibility and keyboard exit repairs pass

PASS for S18. Keyboard-highlighted suggestions scroll only their own list; unmatched combobox Tab/Shift+Tab cancels without committing and restores the owner, preserving outside interaction and valid selection navigation. Grid navigation resolves a hidden active column to a remaining cell without stealing outside focus. Terra reviewed the behavior and Sol confirmed existing one-step cancellation semantics. The 87-case shared grid/layer/editor batch passed 75 cases and exposed 12 editor harness failures because the standalone harness had not installed canonical recorded entry limits. Installing those fixture limits repaired the harness without changing product grammar; all 42 editor cases then passed. Earlier passing grid/layer cases remain applicable to unchanged sources. TypeScript and targeted ESLint pass; sources formatted. The suggestion hover-scroll behavior is retained and is not a blocking defect. Complete application integration remains S17.

### s08-coverage | low | Shared controls and typed editors pass bounded review

PASS for S08 after S18. The shared-control/editor inventory in Scope is covered by the 45 grid/layer and 42 editor cases, including keyboard exit, nested Escape, focus restoration, overflowing choices, locale parsing, date/timezone behavior and served limits. Existing invoice/matching/profile consumers add integration evidence; remaining ledger workflows and whole-app measurement are separately owned by S10/S16/S17. No demonstrated additional shared-control defect remains; browser-locale collation is an optional presentation candidate, not a required repair.

### s09-review | low | Profile and account workflows pass

PASS for S09. The static inventory above is backed by 95 applicable browser cases across user-profile, profiles, manage-profiles, profile-views, profile-completion-notice and titlebar-account. The initial batch passed 94 and timed out looking for the removed profile header fullscreen control. The test now uses the dock's Expand in workspace control; the remaining schema/section-index/autofill case passes. No product change was needed. This covers pending/failed reads, unknown creation, conflict/unknown/saved-unread saves, secret masking, account transitions, deletion confirmation, narrow layouts, translation and focus. TypeScript and targeted lint/format pass for the corrected test.

### s13-static-coverage | medium | Agent workflows expose supported actions; long names needed repair

Terra traced AgentColumn, Composer, Transcript, HistoryList, DocumentsPanel, AttachmentWell/Tile, Approval/Consent/Questions, SkillDialog and AgentSession/Skills contracts. Status/retry, catalogue, local models/license, skills review/verify, conversations, documents, policy, approvals/questions and stream are surfaced. Reply retry and archive restoration remain intentionally unavailable because the host has no such action; attachment availability stays subject to accepted attachment authority. The desktop-agent-host ADR remains proposed, not binding. S26 addresses the two confirmed readability gaps; full conversation/approval/document scenario coverage still belongs to S13.

### s26-review | low | Every sent filename and skill path is readable

PASS for S26. Sol specified full wrapping names, six initial file badges and a native keyboard-operable disclosure for the remainder, with a focusable bounded scroll list; skill paths and sent skill names wrap. Removed the now-unused Transcript locale prop and updated both Storybook consumers. All 24 agent-mentions/agent-skills scenarios pass, including eight filenames, Enter/Space disclosure, remainder focus and long path clipping checks. TypeScript, scoped ESLint and formatting pass. Terra found no concrete source defect; no supported attachment capability was enabled or invented.

### s10-static-coverage | medium | Remaining ledger review found export and counterparty repairs

Terra inspected movement filtering/selection and internal-transfer restrictions; invoices; document intake/read/view/review; accounts, prorrata, capital goods, withholding, rules, ratios, counterparties, diagnostics and health; fixed-asset create/describe/correct/dispose/timeline/plan/claim/handoff; stock books/movements/closing/proofs and preview valuation; import preview/apply/outcomes and export recovery. S27 addresses pending export dismissal and late file picks. S28 addresses counterparty query identity, actual request/response shape, conflict visibility and unsafe recovery assumptions. Invoice catalogue hidden-read cancellation remains a candidate to reproduce. No separate cash/opening-balance workflow was established; do not claim parity without backend mapping. Existing setup, asset, movement, transfer and pause scenarios remain to be integrated with these repairs.

### s14-static-coverage | medium | Local AI read states need truthful presentation and recovery

Terra inspected appearance, terminal layout/font, language, reset/About; provisioning status/plans/progress/cancellation/removal; model list/download/removal/conflicts; providers/sign-in/secrets; conversation provider/model/effort choices. Existing S03/S04 lifecycle fixes remain applicable. Local AI currently collapses provider/catalogue pending or failed reads into no lanes, and a failed model-list read has no in-place retry. Record distinct repair Steps before closing S14; existing local-models, providers, provider-picker, provisioning-recovery and ledger-provisioning scenarios are the verification seams.

### s15-static-coverage | medium | Palette results retain the previous query

Terra inspected DocsFrame origin checks, bounded iframe requests, readiness/malformed replies/timeouts; palette actions/search/deep links; log subscription/source states/filters/export/details; terminal startup/exit/failure/hidden lifetime/input/backpressure/output acknowledgement. Palette rows accepted for query A remain selectable while B is displayed during debounce and request; null docs search also misleadingly says type to search for a nonempty unmatched query. Add a bounded repair before S15 closes. Log resubscription and non-queue-full terminal input recovery are candidates without demonstrated product-loss evidence. Authority: accepted desktop-shell/local docs and docs-terminology-search decisions; no host implementation completeness claim.

### s28-review | low | Counterparty drafts and outcomes follow the real contract

Counterparty lookup replies and drafts now belong to the exact tax ID and optional country. Confirm permits either supported axis, requires an explicit actor under the backend's existing 256-character limit, and preserves edits made during a pending write. The served entry-limit catalogue now exposes that existing bound; backend behavior is unchanged. Withdraw omits the forbidden note field. VIEW supplies resolution only, so the UI no longer invents stored facts or treats a fresh lookup as proof that an unknown write settled. Conflicts show recognized authoritative/proposed values and retain the draft. A settled answer missing requested axes/note also retains it. Backend updates preserve original attribution; differing actor names do not falsely hold a saved draft, and the returned original name is disclosed independently of the follow-up read.

PASS for S28. Sol briefed the actor input and outcome presentation; Terra traced the real request/merge/VIEW contracts and reviewed generation, draft and attribution handling. Seven focused counterparty cases pass after correcting two test interactions: explicitly focusing the formatted country editor before replacement, and locating withdrawal text without assuming an alert role. The additional failed-refresh attribution case also passes after injecting the failure at the actual transport boundary. TypeScript, targeted ESLint and formatting pass. Canonical four-language chrome generation passes, as do scoped Ruff checks and all 47 backend entry-limit tests. Unknown/no-ID settlement remains deliberately unresolved because no exact stored-fact read contract exists.

### s27-review | low | Transfer dialogs retain in-flight ownership and release late picks

PASS for the export/import resource-lifecycle repair. Pending exports cannot dismiss or change destination, format or period. A picker returning after its dialog closes releases every returned token without changing the retired view. Import kind/preview changes wait for a pending picker, and late drop callbacks cannot repopulate an unmounted view. Unknown exports transfer token ownership to the existing write hold. Terra traced navigation guards and native token substitution and withdrew the conditional parent-unmount concern: no same-profile surviving-owner bypass was evidenced.

The initial 70-case setup/transfer/write-pause batch passed 67 cases; its three failures were test assertions/interception. The corrected focused batch passes all 11 cases, including four picker/export regressions. Fixture file hooks now run inside the original file methods, so tests exercise the host's copied methods and actually observe forgetting. Existing transfer and write-pause cases remain applicable. TypeScript, targeted ESLint and formatting pass. No dependency lock or production host contract changed.

## Recommendations

Finish the named repair Steps and append their actual verification and review verdicts here. Extend workflow inventories for S09-S15 and measured performance S16 before final S17 review. Unreviewed workflows remain open.
