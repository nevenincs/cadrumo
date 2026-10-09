---
tags:
  - '#exec'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:e1ea868144987fde6780137c2cc429add83948ee09508459b368ffc5d278e6aa'
related:
  - "[[2026-10-09-desktop-frontend-coherence-plan]]"
---

# `desktop-frontend-coherence` ledger

## Changes

- `S01` `M` `native/desktop/frontend/README.md`
- `S01` `M` `native/desktop/frontend/eslint.config.js`
- `S01` `M` `native/desktop/frontend/package.json`
- `S01` `M` `native/desktop/frontend/src/App.tsx`
- `S01` `M` `native/desktop/frontend/src/components/FilingCalendar.tsx`
- `S01` `M` `native/desktop/frontend/src/components/RecordList.tsx`
- `S01` `M` `native/desktop/frontend/src/components/SignIn.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ui/cn.ts`
- `S01` `M` `native/desktop/frontend/src/components/ui/dialog.tsx`
- `S01` `M` `native/desktop/frontend/src/dev/index.css`
- `S01` `M` `native/desktop/frontend/src/index.css`
- `S01` `M` `native/desktop/frontend/src/shell/layout.ts`
- `S01` `M` `native/desktop/frontend/src/shell/metrics.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/keyboard.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S01` `D` `native/desktop/frontend/src/components/CalendarMonths.tsx`
- `S01` `D` `native/desktop/frontend/src/components/calendarMarks.ts`
- `S01` `D` `native/desktop/frontend/src/shell.css`
- `S01` `D` `native/desktop/frontend/src/theme.css`
- `S01` `D` `native/desktop/frontend/src/tokens.css`
- `S01` `A` `native/desktop/frontend/src/shell/useDesktopEnvironment.ts`
- `S01` `A` `native/desktop/frontend/src/shell/useHostLogs.ts`
- `S01` `A` `native/desktop/frontend/src/shell/useWindowPresentation.ts`
- `S01` `A` `native/desktop/frontend/tests/scenarios/design-system.spec.ts`
- `S01` `A` `native/desktop/frontend/tests/support/terminal.ts`
- `S01` `A` `native/desktop/frontend/dev/eslint/design-system.mjs`
- `S01` `A` `native/desktop/frontend/dev/eslint/styles.mjs`
- `S01` `A` `native/desktop/frontend/dev/eslint/tests/design-system.test.mjs`
- `S01` `A` `native/desktop/frontend/dev/eslint/tests/styles.test.mjs`
- `S01` `A` `native/desktop/frontend/src/components/account/CreateProfile.tsx`
- `S01` `A` `native/desktop/frontend/src/components/calendar/CalendarEntryRow.tsx`
- `S01` `A` `native/desktop/frontend/src/components/calendar/calendarMarks.ts`
- `S01` `A` `native/desktop/frontend/src/components/calendar/CalendarMonth.tsx`
- `S01` `A` `native/desktop/frontend/src/components/calendar/CalendarMonths.tsx`
- `S01` `A` `native/desktop/frontend/src/components/calendar/CalendarTodayMarker.tsx`
- `S01` `A` `native/desktop/frontend/src/components/records/RecordRow.tsx`
- `S01` `A` `native/desktop/frontend/src/styles/base.css`
- `S01` `A` `native/desktop/frontend/src/styles/fonts.css`
- `S01` `A` `native/desktop/frontend/src/styles/shell.css`
- `S01` `A` `native/desktop/frontend/src/styles/theme.css`
- `S01` `A` `native/desktop/frontend/src/styles/tokens.css`
- `S01` `A` `native/desktop/frontend/src/styles/utilities.css`
- `S01` `verify:` `npm run check (TypeScript, ESLint, Prettier and 9 guard tests)` -> `pass`
- `S01` `verify:` `npm run storybook:build` -> `pass`
- `S01` `verify:` `Playwright product build and browser suite (380/382 plus serial rerun 2/2)` -> `pass`
- `S01` `verify:` `Integrated review (token ownership, import direction, stable selectors, font paths and concurrent edit isolation)` -> `pass`
- `S02` `M` `native/desktop/frontend/README.md`
- `S02` `M` `native/desktop/frontend/eslint.config.js`
- `S02` `M` `native/desktop/frontend/dev/eslint/tests/design-system.test.mjs`
- `S02` `M` `native/desktop/frontend/src/App.tsx`
- `S02` `M` `native/desktop/frontend/src/components/FilingCalendar.tsx`
- `S02` `M` `native/desktop/frontend/src/components/RecordList.tsx`
- `S02` `M` `native/desktop/frontend/src/components/calendar/CalendarEntryRow.tsx`
- `S02` `M` `native/desktop/frontend/src/components/calendar/CalendarMonth.tsx`
- `S02` `M` `native/desktop/frontend/src/shell/calendar.ts`
- `S02` `M` `native/desktop/frontend/src/shell/calendarGrid.ts`
- `S02` `M` `native/desktop/frontend/src/shell/records.ts`
- `S02` `M` `native/desktop/frontend/tests/calendar.spec.ts`
- `S02` `A` `native/desktop/frontend/src/shared/dates.ts`
- `S02` `A` `native/desktop/frontend/src/shared/dateFormats.ts`
- `S02` `A` `native/desktop/frontend/src/shell/calendarEntries.ts`
- `S02` `A` `native/desktop/frontend/tests/records.spec.ts`
- `S02` `A` `native/desktop/frontend/tests/shared/dates.spec.ts`
- `S02` `verify:` `npm run check (concurrent titlebar proposal stylesheet drift)` -> `fail`
- `S02` `verify:` `tsc --noEmit; eslint .; node --test dev/eslint/tests/design-system.test.mjs; node --check Tauri launcher; Prettier S02 paths` -> `pass`
- `S02` `verify:` `Playwright product calendar, records and shared dates tests (31)` -> `pass`
- `S02` `verify:` `Playwright affected calendar/log/language browser tests (49)` -> `pass`
- `S02` `verify:` `Playwright production build` -> `pass`
- `S02` `verify:` `npm run storybook:build` -> `pass`
- `S02` `verify:` `Integrated S02 source and dependency review` -> `pass`
- `S02` `verify:` `Final severity defaults/dropdown bindings: TypeScript, full ESLint, scoped Prettier, production build, Storybook build and eight record/browser checks` -> `pass`

## Notes

- `S01` Final fully-parallel workers=3 run: 380 passed, 2 failed (fast-feed timeout and browser `ERR_NO_BUFFER_SPACE).` Exact two-test rerun with workers=1: both passed in 36 seconds. Inputs unchanged. Initial failures and corrected existing test assumptions are detailed in the audit. Native runtime/install checks belong to separate sessions.
- `S02` The complete frontend check fails on another session's titlebar-proposal/proposal.css placement and literal dimensions. Its files are preserved; guards and test scopes are not weakened. S02 required affected-path checks pass. Browser results retained in build/windows-x64/verification/frontend-coherence/helpers-browser-results.json.
