---
tags:
  - '#audit'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:264411850fafdd251f73f7d877120b3a07bfb968830e0255a2b99e4c1e320d9d'
related:
  - "[[2026-10-09-desktop-frontend-coherence-plan]]"
---
# `desktop-frontend-coherence` audit: `Frontend style and component ownership`

## Scope

S01 of the desktop-frontend-coherence plan, reviewed against the accepted desktop design-system and desktop-shell decisions. Baseline bb930c1712; working-tree changes are limited to the frontend refactor, tests, guard configuration and documentation. Concurrent runtime installation edits are excluded from this session's staged scope. Semantic discovery was unavailable because the running index reported index_unverifiable; targeted source reads and the cross-feature decision listing supplied grounding.

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

## Recommendations

PASS. TypeScript, ESLint, formatting, nine guard tests, production build and final Storybook build pass. The final full browser run passed 380 of 382 checks; one fast-feed timeout and one browser net::ERR_NO_BUFFER_SPACE navigation failure both passed in a serial rerun (2/2). These combined results cover all 382 assertions; they are not a claim of a clean single parallel run. Source inputs were unchanged between the full run and serial rerun. Raw initial/final full-run results are retained under build/windows-x64/verification/frontend-coherence; serial rerun output is recorded in the ledger. The reviewed source includes the concurrent installation UI, but this checkpoint stages only the frontend coherence changes. Production builds include bundled fonts and reject development-module leakage. Reuse these checks for future changes; keep actual native authentication, installation and WebView behavior distinct from browser presentation evidence.
