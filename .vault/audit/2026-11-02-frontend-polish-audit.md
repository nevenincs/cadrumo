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

### s29-review | low | Local AI read states and recovery remain truthful

PASS for S29. Setup combines provider settings and catalogue reads under stable session/profile owners and distinguishes pending/failed from successful-empty. The program row and controls remain visible. The agent provider panel also passes catalogue state to every supported keyless lane, including the plural-contract branch. Failed model-list reads have an explicit read-only retry; reset remains reserved for a successfully read but unreadable list. Sol reused existing status/copy/primitives; Terra found no remaining concrete defect. Multiple keyless lanes are supported by the typed contract but the current fixture serves one, so plural-host runtime coverage is not claimed.

All 17 local-model scenarios pass, including delayed catalogue failure, provider-settings failure, read retry without reset, list mutation/revision handling and provisioning/model integration. TypeScript, targeted ESLint and formatting pass. Early new-test failures were corrected by keeping the injected failure active across StrictMode reads and scoping the model retry separately from the program retry.

### s30-review | low | Palette results belong to the current query and provider

PASS for S30. Documentation rows are withheld immediately when their query or search-provider identity differs, including the debounce interval; the existing status line remains outside the listbox. A nonempty unmatched query with no provider says search is unavailable. Shell actions and pasted links retain their behavior. Removed the unreachable loading indicator inside completed result groups. Sol specified the existing presentation and Terra reviewed identity/late-reply handling. All 15 palette scenarios pass, including a clock-paused query replacement and an absent-provider case; the clock resumes after the immediate-removal assertion so the real documentation bridge can finish. TypeScript, scoped ESLint and formatting pass.

### shared-worktree-checkpoint | low | Source changes were included by a concurrent checkpoint

The shared worktree checkpoint f734e601ba included the S27-S30 implementation sources before this session completed its scoped metadata commits; b5554a9db3 and c543d76662 retain the S28/S27 checkpoints. The final 32-case Local AI/palette run passed after the concurrent checkpoint and TUI merge. Unrelated native-modularity plan changes are preserved and excluded from this feature's commits. These source-history boundaries do not substitute for final S17 integration review.

### s19-review | low | Creation uncertainty survives selection and navigation

S19 now keeps creation leases under the existing reader-owned declarations memory, keyed by modelo/year/period, with no request bodies or financial operands. Admission occurs synchronously before submission. Unknown outcomes retain their operation ID when available; Check status observes that operation without resubmitting it. A terminal observation or saved-unread result requires a subsequent successful list read. The list captures only already-complete creation holds and releases only the same unchanged objects after a generation-current success. Running/unknown holds, failed/obsolete reads and cached lists release none. The chooser guards late navigation by live target, port/store generation and mounted lifetime.

PASS for S19. All 16 declarations/list-read browser cases pass, including period changes, navigation/remount, closing during submission, no-ID uncertainty, running status and a failed post-completion refresh. Four pure state tests cover synchronous admission, retired leases, reads begun before completion, changed refresh states and separate reader stores. TypeScript, scoped ESLint, formatting and canonical four-language chrome generation pass. Sol supplied the shared notice/action wording. Terra found no demonstrated blocker and identified a possible late cache refresh of a replacement reader; the callback now marks its captured original memory and rereads only while that reader/memory owner remains current. All five focused lifecycle cases and scoped checks pass after this correction. Concurrent checkpoint 6720e519fc included the initial shared store/notice and locale sources; this Step records the completed creation integration and verification. Work-unit edit/filing/history writers are separately pending S20 and are not claimed fixed by this creation change.

### s10-catalogue-follow-up | low | No cross-profile or unmount exposure established

Terra traced the remaining invoice-catalogue cancellation candidate through LedgerPage and App. Section changes unmount the invoice hook; profile changes remount the ledger by reader. A late response updates only retired hook-local state, not shared memory or the replacement profile. A hidden same-profile view can retain its last result while a new read begins, but the new generation rejects older responses once shown. No reproducible intervening-change defect was established, so this candidate is retired rather than used to justify another repair. The remaining ledger scenario inventory is recorded for S10 integration; this static finding alone does not close that coverage Step.

### s31-s32-integration | medium | Current backend integration prevents complete fixture regeneration

The 105-case Modelo run passed 100 cases. Four Modelo 347 language checks found official context box references still embedded in older fixture labels; current backend and generated contracts expose separate box_number fields, which ContextSummary omitted. S31 renders those fields through BoxNumber with wrapping localized labels. The fifth failure was the S20 refused-apply notice race, repaired and passing in the subsequent focused run. No blanket raw-text assertion was weakened.

Canonical fixture generation exposed three shared-merge integration defects. S32 repairs the fixture producer's unterminated newline literal, restores accepted precedence-divergence attention/gate parity, and mirrors the new internal Decimal export figures through the existing public projection/restoration engine. Contract and relay generation now succeeds; full envelope production still fails where unfinished IVA precedence-screen code passes a bare CalculationSourceResolution to the new tier interface. The TUI integration owner acknowledged this dependency and will supply the finished IVA hash. No registry fixture or runtime response was fabricated to bypass it.

Eleven scoped public-wire and calculation-gate tests pass, including exact decimal text/exponent preservation, strict symmetric schema validation, invalid amount/advisory rejection and persisted blocking-reason parity. The wider 36-test export-offer/gate run passed 13 and failed 23 because the local published authority lacks the newly merged payment-instalment-split and modelo-result-casillas.100 facts. Those authority-dependent integration checks and full fixture regeneration remain open. Terra also identified incomplete persistence handling for the new advisory diagnostic in the unfinished backend feature; this frontend repair does not claim that feature complete.

### s20-review | low | Declaration writers share outcome and refresh ownership

PASS for S20. Calculation, edits, history, correction, export and evidence import now share the reader-owned declaration write hold. A new view cannot resubmit work whose settlement is unknown. Terminal observation invalidates the captured list owner and requires a subsequent current form read; reads begun before completion release nothing. Preflight responses are bound to the write-admission version. Late file-picker results are forgotten, and retired owners cannot navigate or retain returned native file handles. The refused-edit notice survives the end of the request rather than being overwritten by an automatic preflight.

The 17-case focused Modelo run passed. The subsequent final comparison/export run passed six comparison cases and exposed an incorrect test call-counter prefix; after correcting that assertion, the export navigation/status-observation/list-invalidation case passed in 20261102T203445Z-34624. Five pure hold-state tests, earlier scoped TypeScript, ESLint and formatting passed. Terra reviewed the final narrative and terminal-observation corrections without a remaining concrete blocker. Concurrent commit bb0476fd0c contains earlier implementation sources; this checkpoint records the completed behavior, not just that intermediate commit. The unrelated four stale Modelo 347 fixtures remain tracked by S31/S32.

### s21-s33-review | low | Reconciliation exposes differences, limitations and declaration comparison

PASS for S21 and S33. Sol's design uses the existing notice, list, definition-list and disclosure primitives. Every returned difference retains its exact values, including empty versus zero; legal/source identifiers stay selectable text. Advisory limitations are visible even when the limited checks match. The exact narrative remains available in a report-level Returned details disclosure, restoring the prior information without dominating the comparison. The final six comparison scenarios passed in 20261102T201709Z-47552 across four languages and limited/missing-value cases. The English receipt-comparison capture was inspected for readability and wrapping.

The local declaration PDF action uses the backend's existing declaration source kind, current work unit and nullable calculation revision, the native PDF picker and the shared write hold. It does not invent an export prerequisite or a supported-modelo list. Both declaration-comparison transport/refusal/uncertainty scenarios passed in the earlier 17-case focused run. Receipt prerequisites remain unchanged. These are frontend contract and scenario results; positive native PDF reconciliation is not claimed. Canonical four-language chrome, scoped TypeScript, ESLint and formatting passed before the independent AEAT/browser edits began.

### s23-review | low | AEAT progress recovers without claiming stale completion

PASS for S23. Initial observer/read failures have an explicit read-only recovery action. Reconnection invalidates superseded reads and queues refresh requests received while another connection is pending. Pushes mark progress uncertain immediately. Cached terminal results remain readable, but Done, start, resume and retry actions are withheld until current progress is readable, including actions inside Results. Preflight admission is single-use so its callback cannot submit or redirect twice when progress changes. Reader/session-owned actions cannot update a replacement follower.

The full 74-case AEAT/browser run passed 72; all new AEAT recovery cases passed. Its sole AEAT failure came from newly added fixture read logging conflicting with an existing no-action assertion. Removing that unnecessary logging restored the cancellation case in 20261102T205403Z-63704, together with all four focused recovery cases. Combined evidence covers all 44 AEAT scenarios. TypeScript, scoped ESLint, formatting and canonical four-language chrome passed. Terra identified and reviewed the reconnect, preflight and cached-results action corrections. Concurrent WIP checkpoint af80a603c4 captured these source changes while the remaining frontend work was still open; it is not a claim of integrated completion.

### s24-review | low | Browser answers and viewport updates retain recovery

PASS for the changed frontend paths in S24. A JavaScript dialog remains mounted until its answer is accepted. Pending admission, submitted text and failure belong to the native view session, so a remounted prompt cannot admit the same pending answer. The person retries explicitly after failure; no input or answer is automatically replayed. Viewport geometry is recorded only after acceptance, with one in-flight request, the latest desired size coalesced and at most three attempts for one size. Retired sessions cannot update current geometry or prompts. Sol supplied concise inline failure wording; Terra reviewed owner lifetimes and responsive reconciliation.

All 30 existing and added Sede-browser cases now have passing evidence: the full 74-case combined run passed 29 of those 30, including both new resize regressions; the final refused-answer case passed in 20261102T210330Z-45140 after its test stopped trying to navigate through the shell's existing modal navigation guard. The final test covers pending Escape/Enter, preserved text, visible failure and one explicit retry. Hidden/remounted prompt ownership was statically reviewed; that unreachable navigation route is not claimed as runtime coverage. TypeScript, scoped ESLint, formatting and canonical chrome passed. Native host window tests were not repeated for these React-only changes.

### shared-integration-20261102 | medium | Checkpoints and merge state are not verification

External checkpoints af80a603c4 and 2690c28ca1 captured in-progress frontend changes. The following TUI merge left the generated Modelo contract and calculation-note gate test unmerged in the index; frontend verification is held until its owner finishes. S34 help retry and S35 delayed clarification acknowledgement/rejection already have passing focused cases. S35 delayed approval and S36 responsive layout await their corrected test assertions and a stable integrated source tree. No source was reverted to make the shared merge or checks pass.

### s34-s35-review | low | Help recovery and delayed agent replies preserve their current owner

PASS for S34 and S35. Casilla help has an in-place read retry under the existing generic retry label. The hook keys held data by port, work/revision/box/language and retry generation, so obsolete results stay hidden and late reads cannot replace the current card. The successful retry scenario preserves the selected box, confirms served legal text and issues no operation submission.

Agent clarification and approval requests now have synchronous admission and an exact session/reader/conversation owner. Navigation, New conversation, a replacement session and unmount retire the old ticket. A late acknowledgement cannot append text or resolve a prompt in the new conversation; a late rejection cannot restore old text into its composer or clear a newer request's sending state. State updates additionally verify the current interaction ID. Terra reviewed the session-replacement correction and found no remaining concrete owner defect.

All 35 agent-prompt scenarios pass in 20261102T211516Z-51332, including delayed clarification acknowledgement, delayed rejection and an old approval completing while another conversation's decision remains pending. The same batch passed the help-retry case and all nine existing Modelo workspace cases; its only failure was S36's test selector matching both workspace and outline tabpanels. Scoped TypeScript, ESLint and formatting passed before the final tiny selector corrections. A source comparison from 09eab4b79d through the completed corrective merge found no changes in these implementation/test areas, so those results remain applicable. Broader source integration and all-surface validation remain S17 work.

### s36-review | low | One Details panel survives responsive layout changes

PASS for S36. Workspace mounts one Details instance and uses CSS grid placement at wide container sizes. Form, help and staged-action scrolling remain independent. The focused scenario passed in 20261102T214014Z-58260 at viewport widths 600, 1000, 1200 and 1600: one mounted help panel, no additional help reads, reachable staged actions and no workspace horizontal overflow. The 600px and 1600px captures were inspected. Terra reviewed the structure and Sol supplied the responsive placement brief. Scoped ESLint and TypeScript passed after the selector correction; formatting was applied through the configured formatter.

### integration-follow-up | medium | Final source handoff and remaining generation boundary

Corrective merge f5ead5cf98 includes TUI snapshot 3be7987f95 and the previously omitted root changes. Its owner explicitly ended merges and checks. Canonical authority publication succeeded with identity 4096352c94e1913bdfbcbffa2d938e62ace06bc0ea6e64353f1b6ef519242257. Contract generation succeeds. Envelope generation next exposed a real conflict in the synthetic clean-filing setup: it supplied a 13000 prior-income override alongside different seeded filed evidence. The clean helper now omits that redundant override while retaining the separate Renta fixture's explicit answer; regeneration remains in progress. The precedence gate is preserved.

### remaining-recovery-and-wallet-findings | medium | Newly established gaps remain open

Terra retired the speculative ledger cash/opening-balance gap: the identified balances ground imported statement page chains, with no separate ledger operation established. The admitted IVA wallet balance/seed/correct/override operations are a distinct tax-credit capability with no current UI consumer; S39 follows Sol's bounded inline section and existing authority/currentness rules. S37 addresses swallowed browser input refusal without replay or payload retention. S38 adds explicit log subscription recovery; native subscriptions replay a sequenced backlog, requiring deduplication while preserving retained rows and filters. S37-S39 are not yet verified complete.

### s13-s14-state-inventory | low | Conversation and settings coverage awaiting integration runs

S13 static coverage accounts for new/restored/paged conversation history, streaming/queued/waiting-on-person states, send/stop/rename/archive/delete and failed-send draft restoration. Documents and attachments distinguish staged references from stored deletion, empty/loading/failed lists, picker/drop/upload refusals, retry and retired native drops. Skills distinguish loading/failure/empty/no-match, insert tokens through keyboard/pointer selection, and expose details/verification and changed live lists. Provider/model/effort choices cover initial/remembered/no-longer-offered values and unavailable/disabled/empty catalogues. Clarification, consent and operation review preserve host-offered actions and explicit authorization; S26/S35 own the established repairs. Terra identified no additional concrete defect in this bounded pass. Remaining applicable scenario runs are still required.

S14 static coverage accounts for appearance/system theme, terminal presentation, language pending/failure, layout reset, setup and About. Providers expose loading/failed read recovery, successful empty lists, retained status during reread, status distinctions, write-only secrets/base URL, on/off/reset and offered sign-in/cancel flows; S03 fences owner/generation and cached-read version. Provisioning exposes component observations, check loading/failure/unavailable, explicit plan approval/cancel, progress, retry/recovery/removal; closing its panel does not cancel jobs. Local AI separates the machine program from signed-in lanes and withholds person data while signed out. Model lists expose availability/install facts, size/license, add/download/remove, failed reads and conflicts; S29 owns recovery. Multiple keyless lanes are supported by the typed contract and mapped by the UI, but the current fixture supplies one, so plural-lane runtime behavior remains an explicit coverage limit. No further defect was established; canonical integration runs remain pending.

### canonical-modelo-generation | low | Real fixtures now regenerate through the merged backend

Canonical `node native/desktop/frontend/scripts/modelo-fixtures.mjs` passed and wrote all 218 envelopes after the final corrective merge and authority publication. In addition to removing the clean fixture's competing prior-income answer, the stale-export scenario now retains the actual blocking box-06 divergence after its intentional nonzero edit. It no longer attempts to verify that blocked head. Its export stays stale and disabled under the served hold; no diagnostic gate was weakened. The separate Renta caller answer remains intact. TypeScript, targeted ESLint/Prettier, producer Ruff lint/format and canonical chrome pass. Full regenerated Modelo scenarios and scoped Python regression evidence are still pending.

### recovery-focused-verification | low | New browser and logs recovery cases pass

The three new S37/S38 scenarios passed in 20261102T221150Z-42188: one coalesced input-delivery warning with explicit dismissal and no replay; a failed partial log attachment reconnecting without duplicated rows or reset filters; and a reconnect backlog gap exposed separately from reported dropped totals. Terra's final bounded source review found no blocker in session/host ownership, synchronous retry admission or late callback retirement. The same four-case batch's sole failure was an ambiguous stale-export explanation locator, corrected to the file region. Broader logs/browser/Modelo integration is now running; focused results are not a claim that S17 is complete.

### temporary-cleanup-refusal | low | Fixture scratch cleanup was blocked by automatic policy

Five failed-run fixture scratch directories remain under this worktree's `.tmp`: modelo-envelopes-4pBe80, modelo-envelopes-jhox4V, modelo-envelopes-ZNhaXS, modelo-envelopes-oRDRFO and modelo-envelopes-fccYQx. Automatic review rejected both containment-checked cleanup and a narrower command naming only those verified absolute directories with `blocked by policy`. No alternate deletion mechanism was attempted. The successful generator cleaned its own scratch normally. These retained development artifacts are not production inputs.

### s37-s38-review | low | Browser and logs recovery pass integrated scenarios

PASS for S37 and S38. The stable-source run 20261102T221404Z-60704 passed all 165 scenarios: 117 Modelo, 17 logs and 31 Sede-browser. Browser input rejection creates one current-session notice, retains no input payload and never resends it; later successful input does not erase the warning. Logs reconnect only by explicit action, preserves filters and retained records, deduplicates the replayed backlog by native sequence, retires obsolete callbacks and marks an observed missing interval separately from subscription-reported dropped counts. TypeScript, targeted ESLint/Prettier and canonical four-language chrome pass. Terra's final bounded review found no blocker. The shared recovery locale enrollment supports both Steps.

### s12-complete | low | AEAT, calendar, notification and browser workflows accounted for

PASS for the frontend scope of S12. The inventory includes connection/sign-in prerequisites; per-area current/stale/unavailable and last-attempt state; local read retry; selected/all preflight and assisted sign-in; not-started/waiting/running/failed/unknown/completed progress; cancellation after current work; pause/resume; explicit acknowledged retry; and confirmed-empty versus partial/unavailable results. Notifications retain unread/read and link to the Sede for person action. Comparison differences and local Borrador PDF import keep refused, unknown, superseded and active outcomes distinct. Calendar accounts for dated entries, missing filing windows, undetermined applicability and registry advice without hiding advice beside obligations. Browser accounts for lifecycle, toolbar/clipboard, downloads/choosers, dialogs, acquisition, current-session visibility, bounded viewport retry and input-delivery uncertainty.

Evidence combines the unchanged 44 AEAT cases, six calendar cases including four-language advice, the prior profile-view lifecycle regression and the current full 31-case browser run. S23/S24/S37 close the established recovery findings. These are simulated-host frontend results, not live AEAT traffic, native engine/picker/certificate verification or submission evidence. Native input admission does not prove page effect, and person-driven AEAT submission stays separate. Terra found no remaining concrete S12 candidate in the bounded review.

### s32-public-contract-review | low | Canonical export offers replace the redundant public mirror

The merged canonical election figures already carry validated decimal strings. The public workbench projection now uses the canonical export-offer model directly, removing the duplicate model and conversion layer. Its real calculated-form roundtrip retains exact `600.01` and `400.00` text, rejects malformed, negative, over-precision and numeric amounts, and preserves the existing grammar's accepted `01.0` text. The test's read identity now matches its calculated form; production identity checks remain unchanged. The redundant mirror-only test was removed and its cross-field rejection moved into the real roundtrip test.

The five-file Python batch passed 158 cases; its remaining test passed after those test-assumption corrections in 20261102T224730.788816Z-pytest-11892-216f1d3c. Scoped Ruff lint/format and frontend TypeScript, ESLint and Prettier pass. Terra confirmed the canonical grammar and reviewed the removal's consumers. Canonical `modelo-fixtures.mjs --check` passes after simplification. The current generated contract and all 218 envelopes validate without compatibility shims or altered dependency locks.

### s31-context-boxes-review | low | Served context box numbers survive canonical regeneration

PASS for S31. RecordsBlock renders the backend's context-fact box numbers alongside their returned values. The canonical 218-envelope refresh now includes the current contract, and all 117 Modelo browser cases passed in 20261102T221404Z-60704, including the Modelo 347 context-box assertions in all four supported languages. Subsequent export-offer type simplification preserves the fixture wire shape and passes canonical validation. RecordsBlock implementation was already retained in the corrective merge; this closes its generation and regression verification.

### s40-filing-explanations-review | low | One shared refusal preserves each affected action's explanation

PASS for S40. FilingView presents the common export hold once above its action sections and links matching unavailable actions and named sections through `aria-describedby`. Only exact repeated text disappears. Distinct file, record and copy refusals remain, as do stale-file provenance and receipt state; comparison is not associated with the export hold. The earlier implementation also hid a distinct file refusal whenever any export hold existed; that reason now remains visible.

All 15 focused filing, receipt and comparison scenarios passed in 20261102T231110Z-60104, including shared-description assertions, distinct-refusal preservation and four-language receipt comparisons. The shared-hold screenshot was inspected: the warning and Open Check action precede the file card; the stale-file notice and available PDF comparison remain visible. TypeScript and scoped ESLint/Prettier pass. Terra reviewed information preservation against the Sol brief and found no blocker. The first browser attempt timed out during canonical server startup while unrelated lanes saturated the machine; no case ran in that attempt. The passing batch ran after all owners confirmed the quiet window.

### s16-measurement-baseline | medium | Valid benchmark exposes asset size and calendar opening costs

S16 remains open. The old benchmark waited for DOM terminal rows that WebGL does not create, looked for a log severity select outside its new Filters popover, and served a static scenario page without the Docs fixture port. Its Docs pane therefore failed rather than contributing the intended workload. The harness now uses the canonical Vite scenario preview and fixed configured ports, checks the actual Docs frame, uses the shared terminal-screen seam after a frame, opens the real Filters control, and does not wait for an unactivated console when Logs is restored. Its explicit Docs/TUI/console layout, visible dock-divider interaction, failure snapshot and phase output make the measured setup reviewable. The underlying budgets were not changed.

The final quiet-window run at 2026-11-02T23:21:21.199Z completed every phase. FAIL: product JavaScript 1038.9 KiB gzip against 320, CSS 21.8 KiB against 20, calendar shown median 701 ms against 150. Other budgets passed: first paint 272 ms, terminal readiness 350.5 ms, idle heap 21.7 MiB, palette median 29.3 ms, 10,000-log first rows 52.9 ms/filter 35.9 ms/heap 31.6 MiB, and 5,040 ledger movements read and drawn in median 318.7 ms with 37 rendered rows and 42.4 MiB heap. Dock/log frame p95 was about 16.8 ms; ledger p95 was 33.4 ms. Forty-cycle calendar and sign-in churn left zero added nodes/listeners; overlay counts did not grow. These are minified scenario-host timings and product emitted-byte totals, not native/live data performance.

All six other owner lanes explicitly drained before this run; the shared heavy-run hold was explicitly released afterward and the coordinator confirmed relaying it to all six owners. Earlier runs during CPU saturation or with a failed Docs pane are not substitutes for this baseline. Terra identified repeated locale keys across the four generated catalogues as a reducible payload candidate; its representation estimate is not an implemented or verified saving.

The raw 701 ms calendar value is not yet a demonstrated product delay. Subsequent static tracing found that closing the calendar can return focus to the Docs iframe, while the timing listener only observes the parent window. A missed key leaves its old start value at zero and measures page age. The harness now focuses a parent-window rail control before timed input and refuses a sample with no captured key timestamp; runtime remeasurement is pending. No calendar runtime code was changed on the basis of that questionable sample.

### S39 integrated review and verification, 2026-11-03

Terra review found that `iva_wallet_decision` is a mesh-only route, not a registry field-binding source; source groups cannot serve as a wallet capability flag. The wallet entry now follows the served Modelo 303 identity, including an uncalculated declaration, while the runtime admits each register operation. No fabricated source rows or recalculation are introduced to make it visible.

The root implementation withholds balance figures during any conflicting write, retains outcome ownership after modal closure, and requires both balance and owning-declaration reads before releasing a wallet refresh hold. Sol reviewed compact receipt facts: returned provenance and nullable register status for seed/correction, selected authority and divergence for override. Null status reads “Not reported”, not a registration claim. Unknown future receipt tokens remain visible.

Canonical generation and final `modelo-fixtures.mjs --check` pass with 245 envelopes. Each wallet stage captures the same profile's 303 without recalculation. The 850.00 override remains a separate decision: the corrected lot balance remains 900.25. The model-specific tab is “IVA balance”; the existing Renta withholding label is preserved.

Final TypeScript, scoped ESLint/Prettier, Ruff, chrome generation and nine hold unit cases pass. Three catalogue packing unit cases also passed and belong to the separate S41 evidence. The first wallet run had seven passes and one Catalan startup failure; its trace records `net::ERR_NO_BUFFER_SPACE` fetching React before application startup. The subsequent broader run `20261103T000737Z-27288` had 98 passes and five failures caused by wrapping creation-dialog opens in the global navigation guard. The fix separates direct list/creation opens from guarded workspace-to-workspace owner links. Do not report that run as a full pass.

The final focused run `20261103T001331Z-28880` passes all 14 cases: nine wallet cases plus all five previously failing incomplete-model opens. Wallet coverage includes all four locales, exact decimal requests, separate action drafts, returned provenance/authority, no automatic recalculation, pending-dialog closure with visible owner, unknown settlement without resubmission, failed balance and form recovery, foreign owner links with staged-edit cancel/discard, and a delayed old-year response. Follow-up run `20261103T001600Z-29224` passes all 24 declaration/workspace/profile regressions, including creation holds, Renta withholding routing, and late profile reads. Narrow balance and override receipt screenshots were inspected.

Terra's final bounded integrated review finds no blocker against the wallet, aggregation, carry and desktop authority decisions. These browser scenarios use a synthetic host; canonical producers exercise the actual operation executors, but this is not live native-wallet or AEAT verification. Backend refusal remains authoritative for unsupported requests, and an unknown operation without an identifier remains unresolved. S39 is ready to close; overall Modelo and integrated frontend coverage remain separate open work.

### S41 catalogue payload review, 2026-11-03

PASS for the bounded encoding change. The build shares the four catalogues' identical ordered key vector and reconstructs the existing synchronous locale maps. Canonical locale JSON, translation ownership, fallback/token behavior and the development file/HMR route remain unchanged. Malformed values or differently ordered locale keys stop the build. The generated file remains a watched input; no generated source or translation is hand-maintained.

The three direct unit cases pass: exact canonical catalogue round-trip and order; special own keys, empty values, placeholders, Unicode and script-delimiter escaping; and refusal of malformed/mismatched catalogues. TypeScript, scoped ESLint/Prettier, and the product build passed. The four-language built-scenario cases subsequently passed, including the new wallet labels. Terra's bounded review found no blocker and classified this as build encoding under the accepted localization decision, not a new catalogue or loading authority.

Within the same pre-S39 product-build cohort, Node gzip totals for all emitted JavaScript fell from 1,063,818 to 951,984 bytes: 111,834 bytes (10.5%) removed without removing strings. CSS remained 22,366 bytes. The retained product artifact confirms 704,131 bytes for the main chunk, 247,115 for the catalogue-bearing chunk and 738 for startup. This is emitted-payload evidence, not a claim about the later wallet cohort's total bytes or native startup speed. S16 remains open: the overall JavaScript/CSS budgets still fail, the corrected calendar timer needs remeasurement, and further main-chunk reductions require actual module attribution rather than guessing from xterm/WebGL identifiers.

### S42 delayed confirmation focus, 2026-11-03

PASS for the bounded focus repair. The ledger integration run `20261103T001922Z-56856` completed 175 cases with 171 passes and four failures. The document-confirmation failure was a real race: the effect focused the confirmed result before its asynchronous matching link existed. A stable callback ref now focuses the arriving link only while that same result still owns focus. It neither steals focus after the person moves nor changes the confirmation or matching write.

TypeScript and scoped ESLint/Prettier pass. Run `20261103T003007Z-26936` passes the existing confirmation/Enter-to-stage case and both explicit deferred-match cases (remain at result; move focus elsewhere). Terra's bounded review finds no blocker. That six-case run passed five and failed one; it is not a wholly passing run. The editing-row failure was corrected by searching for the virtualized row before editing, and the obsolete pane-title assertion now checks the owning dock tab. The remaining geometry test confirms the dock can compress the ledger scrolling band behind its pinned columns; S43 owns that separate repair. S10 remains open.

## Recommendations




Finish the named repair Steps and append their actual verification and review verdicts here. Extend workflow inventories for S09-S15 and measured performance S16 before final S17 review. Unreviewed workflows remain open.
