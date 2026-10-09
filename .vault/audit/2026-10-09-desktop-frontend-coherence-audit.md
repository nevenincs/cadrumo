---
tags:
  - '#audit'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:df8cc009c5c51fce689b9003b881ffe989e0848b1136317d0261e51d69a9d216'
related:
  - "[[2026-10-09-desktop-frontend-coherence-plan]]"
---
# `desktop-frontend-coherence` audit: `Frontend style and component ownership`

## Scope

S01 of the desktop-frontend-coherence plan, reviewed against the accepted desktop design-system and desktop-shell decisions. Baseline bb930c1712; working-tree changes are limited to the frontend refactor, tests, guard configuration and documentation. Concurrent runtime installation edits are excluded from this session's staged scope. Semantic discovery was unavailable because the running index reported index_unverifiable; targeted source reads and the cross-feature decision listing supplied grounding.

S02 continues the user-authorized audit under the same decisions. Its source review is based on e36494d2ea plus the owned helper changes; concurrent titlebar proposal files are excluded. Semantic search again reported index_unverifiable, so targeted reads supplied grounding.

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

## Recommendations

PASS. TypeScript, ESLint, formatting, nine guard tests, production build and final Storybook build pass. The final full browser run passed 380 of 382 checks; one fast-feed timeout and one browser net::ERR_NO_BUFFER_SPACE navigation failure both passed in a serial rerun (2/2). These combined results cover all 382 assertions; they are not a claim of a clean single parallel run. Source inputs were unchanged between the full run and serial rerun. Raw initial/final full-run results are retained under build/windows-x64/verification/frontend-coherence; serial rerun output is recorded in the ledger. The reviewed source includes the concurrent installation UI, but this checkpoint stages only the frontend coherence changes. Production builds include bundled fonts and reject development-module leakage. Reuse these checks for future changes; keep actual native authentication, installation and WebView behavior distinct from browser presentation evidence.

S02: PASS for the reviewed helper consolidation: 31 pure helper/calendar/record checks, 49 affected calendar/log browser checks, seven design-system guard tests, TypeScript, ESLint, scoped formatting, Tauri launcher syntax, production builds and Storybook build. The complete frontend check remains FAIL on the separately edited prototype stylesheet described above. Reconcile that sheet through its owner before claiming a clean whole-checkout gate. The prior S01 results above remain historical evidence for that checkpoint.
