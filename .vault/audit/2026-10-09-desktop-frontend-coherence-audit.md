---
tags:
  - '#audit'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:3ecaffcfa354ac87300652bae4a3626793eff2defd80d8d7438124e29c7d019b'
related:
  - "[[2026-10-09-desktop-frontend-coherence-plan]]"
---
# `desktop-frontend-coherence` audit: `Frontend style and component ownership`

## Scope

S01 of the desktop-frontend-coherence plan, reviewed against the accepted desktop design-system and desktop-shell decisions. Baseline bb930c1712; working-tree changes are limited to the frontend refactor, tests, guard configuration and documentation. Concurrent runtime installation edits are excluded from this session's staged scope. Semantic discovery was unavailable because the running index reported index_unverifiable; targeted source reads and the cross-feature decision listing supplied grounding.

S02 continues the user-authorized audit under the same decisions. Its source review is based on e36494d2ea plus the owned helper changes; concurrent titlebar proposal files are excluded. Semantic search again reported index_unverifiable, so targeted reads supplied grounding.

S03 reviews the explicitly requested titlebar visual-study alignment against the same accepted design-system and shell decisions, based on c3d6a0db46 and its owned working-tree changes. Concurrent native titlebar implementation and its scenario-entry integration are separate ownership. The new native titlebar decision was read; this step changes no window API or authentication authority. Semantic discovery remained index_unverifiable.

## Findings

### style-ownership | medium | Resolved scattered sheets and independent component dimensions

The source root formerly held tokens, role mapping and shared imports. Calendar bars and month/list grids, log columns and dialog limits embedded literal lengths. These now resolve through src/styles/tokens.css and token-backed utilities, shared by product, scenario and catalogue entries. Typeface URL containment was adjusted for the new directory. Base focus and reduced-motion rules have their own owner. System colors and computational zero values remain valid; xterm's existing ANSI palette exception remains confined to shell/terminalThemes.ts.

### module-ownership | medium | Resolved mixed presentation and subscription responsibilities

CalendarMonth, CalendarMonths, CalendarEntryRow and CalendarTodayMarker now live under components/calendar with shared mark/tone data. RecordRow lives under components/records. Profile creation lives under components/account. Environment reads, log subscriptions and window presentation listeners have focused shell hooks that retain the prior cancellation and unsubscribe behavior. The public SignIn.tsx path is preserved for the concurrently edited installation controls. Definitions and consumers moved together; no forwarding modules were added.

### guard-coverage | low | Added mechanical checks with negative fixtures

ESLint rejects literal component/story style scales, inconsistent React filenames, component imports of App, upward primitive imports and re-exports. Filesystem-based checks reject misplaced CSS and independently authored dimensional/color scales outside their owners. Negative fixtures exercise representative violations rather than merely matching current output. Browser probes change overlay, log-column and calendar-month tokens and measure the actual rendered result.

### verification-drift | low | Resolved existing assumptions about terminal rendering and log details

The initial full run passed 368 of 379 checks and exposed ten existing test assumptions plus one edit regression. HEAD inspection confirmed structured metadata makes multiple rows expandable, generated measurement records all have metadata, WebGL has no xterm-rows DOM, and AccountLoading uses account-loading instead of empty. Keyboard assertions now identify the traceback record explicitly; no-detail coverage uses a genuinely context-free fixture; paging checks viewport travel instead of assuming row height; terminal text scenarios use the real DOM fallback while product rendering tests continue to exercise WebGL. No acceptance assertions were skipped and no product error/detail information was suppressed.

### text-encoding | medium | Resolved an edit-script encoding regression

A Windows-default text read in this session transposed the calendar separator and documentation/token comments. Explicit UTF-8 reads restored the original text. The calendar observation assertion passed again after the repair. Subsequent source reads use an explicit encoding.

### shared-helper-ownership | low | S02 consolidated reusable date and record rules

Continued inspection found repeated local ISO-date formatting, independent day parsing/arithmetic, repeated Intl date/relative format options, duplicated calendar state ordering and independent severity ranking in the log list and its menu. shared/dates.ts now owns date-only conversion and UTC ordinals; shared/dateFormats.ts owns named formatter bundles with a bounded 16-locale least-recently-used cache. calendarEntries.ts owns product-specific entry identity, filing spans and urgency, without making presentation depend on grid layout. records.ts supplies one severity rank with null treated as INFO. All defining modules and their consumers moved together; no re-exports or forwarding aliases were retained. A tested ESLint boundary keeps shared helpers independent of components, shell policy, IPC and host APIs. The date ordinal removes local clock duration from calendar-day distances, including Samoa's skipped local day in 2011.

### intentional-owner-differences | low | S02 retained distinct interaction and read policies

Focus restoration and calendar/log scroll positioning have different element, anchoring and keyboard requirements. Messages and calendar reads differ in when they ask, freshness intervals and profile-visible state. Timestamp serialization for log records differs from localized calendar labels. These remain with their owners; already-shared fromPointer, revealFocused, recordContext and failureCode were reused as existing ownership evidence. No generic focus, refresh or serialization facade was introduced.

### concurrent-prototype-styles | low | S02 identified style drift in another session's titlebar proposal

The complete npm run check passed TypeScript and ESLint and seven design-system guard tests, then failed the filesystem style guard on src/dev/titlebar-proposal/proposal.css: the sheet is outside src/styles and declares literal dimensional scales. This file and the related ScenarioBar/main edits were being authored by another session and are excluded from this checkpoint. The guard remains unchanged and still reports the drift. Separate checks passed full TypeScript and ESLint, the seven design-system guard tests, Tauri launcher syntax and formatting of all S02 paths. This is scoped verification, not a claim that the complete working-tree check passes.

### severity-bindings | low | S02 removed remaining numeric severity thresholds

The final caller review also replaced numeric thresholds in the filter dropdown and DEFAULT_FILTERS with levelRank calls; the ordering array is now private to records.ts. After these final edits, TypeScript, full ESLint, affected-path Prettier, production and Storybook builds passed again, as did all eight affected record/filter/diagnostic checks. Their raw result is retained in helpers-records-browser-results.json beside the earlier 49-check run. Date, formatter and calendar source inputs were unchanged, so their passing evidence is reused.

### titlebar-style-alignment | low | S03 resolved the prototype style drift

The visual study now imports src/styles/titlebar-proposal.css. Names are titlebar-prefixed, caption glyph selectors are scoped to their placeholder, and composition rules sit in the components layer. tokens.css owns header geometry and the two rem query thresholds; the separately compiled sheet references those definitions without emitting a second token owner. The profile trigger uses the shared Button through Radix asChild, preserving density, focus and disabled behavior instead of independently styling a raw button. It can shrink so long profile names clip without pushing window placeholders out of view. Existing cap-height trimming for the logo wordmark is preserved.

### titlebar-render-verification | low | S03 verified actual responsive layout and production isolation

Eight titlebar browser checks cover three platform layouts at 1440 and 360 CSS pixels, control order and disabled state, visible content center alignment and containment, signed-out long-profile clipping, readable bounded menus, Escape focus restoration and a changed titlebar-height token. Three existing design-system browser checks and five product bundle checks also pass. Production-byte assertions explicitly exclude the proposal's header and menu selectors after its sheet moved outside the dev folder. Wide and narrow screenshots were inspected. The initial run exposed a missing Tailwind variant reference and an incorrect test assumption that the signed-out shell had no credential modal. The variant reference is fixed; the test now dismisses the real credential dialog before interacting and after a mock-profile restart, without bypassing its focus trap.

### titlebar-promotion-and-cascade | low | S03 followed the concurrent application promotion and resolved control geometry drift

After the prototype checks passed, the separate titlebar implementation session promoted the header into App and retired the untracked visual-study module and sheet. S03 was reopened and its scope corrected through the plan verb. The application titlebar.css now references the central compact/narrow variants instead of introducing 700px and 480px scales. Concurrent insertion briefly duplicated the identical titlebar-height declaration; one remains. The promoted sheet's components layer let Button utility sizing override window-control geometry (measured width 36 rather than the overridden token's 64). The scoped control and profile-trigger customizations now occupy the utilities layer with selector specificity that overrides the primitive size/shrink defaults while keeping its focus and interaction styles. The four final titlebar-layout checks exercise application composition rather than the retired mockup.

## Recommendations

PASS. TypeScript, ESLint, formatting, nine guard tests, production build and final Storybook build pass. The final full browser run passed 380 of 382 checks; one fast-feed timeout and one browser net::ERR_NO_BUFFER_SPACE navigation failure both passed in a serial rerun (2/2). These combined results cover all 382 assertions; they are not a claim of a clean single parallel run. Source inputs were unchanged between the full run and serial rerun. Raw initial/final full-run results are retained under build/windows-x64/verification/frontend-coherence; serial rerun output is recorded in the ledger. The reviewed source includes the concurrent installation UI, but this checkpoint stages only the frontend coherence changes. Production builds include bundled fonts and reject development-module leakage. Reuse these checks for future changes; keep actual native authentication, installation and WebView behavior distinct from browser presentation evidence.

S02: PASS for the reviewed helper consolidation: 31 pure helper/calendar/record checks, 49 affected calendar/log browser checks, seven design-system guard tests, TypeScript, ESLint, scoped formatting, Tauri launcher syntax, production builds and Storybook build. The complete frontend check remains FAIL on the separately edited prototype stylesheet described above. Reconcile that sheet through its owner before claiming a clean whole-checkout gate. The prior S01 results above remain historical evidence for that checkpoint.

S03: PASS. npm run check passes TypeScript, full ESLint, all ten guard tests, Tauri launcher syntax and full frontend/sibling formatting. Production and Storybook builds pass. The final focused product/scenario run passes all 16 checks on the final source inputs. Raw initial, intermediate and final results plus titlebar-wide.png and titlebar-narrow.png are retained under build/windows-x64/verification/frontend-coherence. S03 resolves the concurrent-prototype stylesheet failure recorded historically for S02. The native product titlebar and actual authentication remain owned by their separate implementation session; this review establishes visual-study composition and shared style conventions only.

S03 final application review: PASS for the committed style/alignment scope. The final application titlebar, design-system and product bundle run passes 12/12; production and Storybook builds pass. Prior prototype results above are historical and are superseded for current rendering by titlebar-application-final-results.json. The complete frontend check initially failed formatting on the concurrently updated SignIn.stories.tsx; formatting was applied without staging that file, and the complete check was rerun. That later check passes TypeScript, full ESLint, all ten guards and launcher syntax, then fails formatting on six actively edited native-titlebar files: AccountMenu.tsx, accountWords.ts, SignIn.tsx, ipc/contract.ts, shell/signIn.ts and shell/tauriHost.ts. The three committed style/test paths pass a separate final scoped Prettier check. This is scoped PASS and a reported full-check FAIL, not a claim that the actively changing checkout has a clean complete gate. Current application wide/narrow screenshots were inspected. Native window APIs, account controller changes and the production header component remain the separate session's source scope. The checkpoint commits only tokens.css, titlebar.css, bundle.spec.ts and this feature's plan/audit/ledger. The transient application layout probe is retained as titlebar-layout.spec.ts under the verification directory, so this checkpoint does not add a test that depends on the other session's uncommitted Titlebar component. Existing filesystem drift guards and product bundle assertions remain permanent coverage; the native titlebar session owns lasting application interaction tests.
