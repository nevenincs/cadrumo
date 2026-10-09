---
tags:
  - '#exec'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:74a7fd098f5584b9fc01c04736098147d54781f4c04e5de95d39670e8c1e8c0a'
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
- `S03` `A` `native/desktop/frontend/src/dev/titlebar-proposal/TitlebarMockup.tsx`
- `S03` `A` `native/desktop/frontend/src/styles/titlebar-proposal.css`
- `S03` `M` `native/desktop/frontend/src/styles/tokens.css`
- `S03` `M` `native/desktop/frontend/tests/bundle.spec.ts`
- `S03` `A` `native/desktop/frontend/tests/scenarios/titlebar.spec.ts`
- `S03` `verify:` `npm run check (TypeScript, full ESLint, ten guards, launcher syntax and full formatting)` -> `pass`
- `S03` `verify:` `npm run build` -> `pass`
- `S03` `verify:` `npm run storybook:build` -> `pass`
- `S03` `verify:` `Playwright titlebar, design-system and product bundle checks (16)` -> `pass`
- `S03` `verify:` `Integrated S03 style, composition and isolation review with screenshot inspection` -> `pass`
- `S03` `D` `native/desktop/frontend/src/dev/titlebar-proposal/TitlebarMockup.tsx`
- `S03` `D` `native/desktop/frontend/src/styles/titlebar-proposal.css`
- `S03` `D` `native/desktop/frontend/tests/scenarios/titlebar.spec.ts`
- `S03` `A` `native/desktop/frontend/src/styles/titlebar.css`
- `S03` `verify:` `Application titlebar layout probe plus design-system and bundle checks (12)` -> `pass`
- `S03` `verify:` `Final application Storybook build` -> `pass`
- `S03` `verify:` `Full frontend check during concurrent native header edits (formatting in six active source files)` -> `fail`
- `S03` `verify:` `Final stylesheet guards and scoped tokens/titlebar/bundle Prettier` -> `pass`

## Notes

- `S01` Final fully-parallel workers=3 run: 380 passed, 2 failed (fast-feed timeout and browser `ERR_NO_BUFFER_SPACE).` Exact two-test rerun with workers=1: both passed in 36 seconds. Inputs unchanged. Initial failures and corrected existing test assumptions are detailed in the audit. Native runtime/install checks belong to separate sessions.
- `S02` The complete frontend check fails on another session's titlebar-proposal/proposal.css placement and literal dimensions. Its files are preserved; guards and test scopes are not weakened. S02 required affected-path checks pass. Browser results retained in build/windows-x64/verification/frontend-coherence/helpers-browser-results.json.
- `S03` The existing untracked visual study was aligned at the user request. Its untracked proposal.css was moved into styles; concurrent ScenarioBar/main integration and native titlebar work remain unstaged.
- `S03` The native titlebar session retired the untracked prototype during S03. The Step was reopened and corrected to application stylesheet geometry. Initial prototype rows are historical; final checkpoint source paths are tokens.css, titlebar.css and bundle.spec.ts. The transient application layout probe is retained in the ignored verification directory to avoid committing tests that depend on another session uncommitted native header implementation. Full-check formatting failures are reported in the audit; native and account source work remains unstaged.
