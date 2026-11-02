---
tags:
  - '#audit'
  - '#frontend-polish'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:5135155612044ad2b9c1520c21c7b41e1ba1b4d73ec8a2a661cc5f332619b036'
related:
  - "[[2026-11-02-frontend-polish-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace frontend-polish with a kebab-case feature tag, e.g. #foo-bar.
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

# `frontend-polish` audit: `Frontend workflow coverage and hardening`

## Scope

Application-wide frontend hardening under the approved frontend-polish plan. Root implements; Terra performs read-only workflow discovery and Sol designs confirmed presentation gaps. This rolling record distinguishes static review from browser evidence. It is not yet a completed application-wide audit.

S08 static coverage: shared buttons, inputs, textarea, native select, field, calendar, combobox, suggestions; dialog, sheet, popover, dropdown menu, escape layers, reveal, tabs, radio, switch, toast, alert; table-view, data-grid header/row, keyboard/viewport/navigation/selection, checkbox, text-tip and segmented control; typed editor dispatch, EntryInput, TypedField, Date, Code, Notes, Percent, number reading, fieldCheck and editor props. Traced consumers include profile code suggestions, ledger classifications, invoices, documents, assets and grid cells. Remaining evidence: browser reproductions and fixes below, integrated consumers and performance measurement. Static coverage alone does not close S08.

S11 static workflow coverage: declarations list and creation targets; WorkspaceScreen and form/baseline loading; Form, Details/Todo, Check, Sources, History/corrections and Filing; staged edits, preflight, one stale-baseline renewal, apply, calculate/verify, local export, local filing records and justificante import. Reviewed useEditReview, form/session and filing/modelo contracts. Authority includes accepted desktop-modelo-workspace, modelo-editor-workbench-operator-layer and filing-chain-reconciliation decisions. No AEAT submission is implemented or inferred. Remaining evidence: settlement fixes, structured reconciliation details and integrated scenario checks.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Frontend workflow coverage and hardening | {level} | {summary}

     followed by a paragraph carrying the detail. Frontend workflow coverage and hardening is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

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

## Recommendations

Finish the named repair Steps and append their actual verification and review verdicts here. Extend workflow inventories for S09-S15 and measured performance S16 before final S17 review. Unreviewed workflows remain open.

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
