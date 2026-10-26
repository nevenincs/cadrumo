---
tags:
  - '#plan'
  - '#desktop-design-system'
date: '2026-10-05'
tier: L2
related:
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
modified: '2026-10-05'
body_schema: body-v2
body_hash: 'sha256:48397680b64b160f8537c32f8d41a96946e3a84a8b53b9e320b62910c2984c79'
---

# `desktop-design-system` plan

## Description

Approved 2026-10-05

Authorization basis: the user's 2026-10-05 frontend design handover brief to this session, confirmed the same day by the stated goal: build the complete design system and its dependencies for the Tauri application with React, shadcn, Tailwind 4, Radix and Storybook 10; apply UX principles, simplicity and one harmonized design; keep it variable, argument, em and rem driven, modern, reactive, responsive and optimized, with proper event handling; and use design review agents at checkpoints.

### Decision coverage

- `2026-10-05-desktop-design-system-adr` governs every Step: the dependency set, the token and ownership layers, the icon library, the development scenario host and its absence from the product, the sign-in dialog presentation, the display-language setting, the stable hooks and the catalogue. Its evidence is `2026-10-05-desktop-design-system-reference`.
- `2026-10-04-desktop-shell-adr` governs layout, keymap, bridge, palette contents, settings items, theme source and the rule that the bundle names no location or environment variable. No Step changes the IPC contract, the bridge protocol or the keymap.
- `2026-10-04-application-sign-in-adr` governs sign-in behaviour. P03 changes presentation only; `src/shell/signIn.ts` keeps its single submission, status serialization and no-retry rules.

No further costly decision is expected. A new host command, a keymap change or a new string family beyond the keys this plan names goes back to the user.

### Boundaries with open plans

`2026-10-04-desktop-shell-plan` S09 (shell frontend for the v2 layout) stays open under its own owner record; this plan restyles and recomposes what S09 built and does not close it. `native/desktop/src-tauri/**` and `native/desktop/tests/**` belong to the desktop host lane and are not edited here; the hooks its packaged suite reads are preserved. Locale catalogues under `src/cadrumo/locales/` are shared with other sessions: new keys go through `dev.locales set-batch`, and commits stage only this plan's hunks.

### Design rules every Step holds

- Lengths in rem, or em where a control should scale with its own text; the hairline and the focus ring are the only pixel lengths. No colour value outside the generated palette, the theme stylesheet's alphas and the terminal palettes.
- A component takes its variation through typed props and variants, never through a one-off class or inline dimension.
- State is derived, not mirrored; effects clean up every listener, timer and observer they add; pointer and keyboard paths reach the same handler.
- Every interactive control has a visible focus state, an accessible name, and works by keyboard. Motion honours `prefers-reduced-motion`.
- Layout holds from a 520 px wide window to a large desktop, at 200 percent root font size, and with the longest of the four locales' labels.

### Checkpoints

Each Phase closes with a design review by an independent agent that reads the changed code and browser screenshots against these rules and the governing decisions. High findings are fixed before the next Phase starts; the findings are appended to the feature's rolling audit.

### Purpose

Rebuild the desktop shell's presentation on one design system (shadcn/ui on Radix, Tailwind 4, Storybook 10) developed in a browser against deterministic host scenarios.

## Steps

### Phase `P01` - browser development loop

A fresh checkout reaches a hot-reloading shell in a browser with selectable host scenarios, and the product build contains none of the scenario code.

- [x] `P01.S01` - Document and prove the lightweight bootstrap that configures the standalone desktop project and runs the existing chrome-string and palette generators, so the development server starts on a fresh build directory without Rust, a wheel or a documentation build, and record the browser development commands; `native/desktop/frontend/README.md (new), native/desktop/frontend/package.json scripts`.
- [x] `P01.S02` - Add the development-only scenario host implementing Host with deterministic signed-out, signing-in, signed-in, wrong-password, throttled, runtime-unavailable, loading, empty and error scenarios, mounted from a separate development entry page with a labelled scenario switcher, a deterministic terminal fixture and a separate-origin documentation fixture, and prove by a test on the built output that the production bundle contains none of it; `native/desktop/frontend/scenarios.html (new), native/desktop/frontend/src/dev/ (new), native/desktop/frontend/vite.config.ts, native/desktop/frontend/tests/`.

### Phase `P02` - tokens, primitives and catalogue

One theme bound to the generated palette, the shared primitives every surface composes, and a Storybook catalogue of their states.

- [x] `P02.S03` - Add the pinned design-system dependencies and the Tailwind 4 integration, and reconcile the stylesheets into one theme that maps the generated palette to semantic roles on every scheme boundary and exposes the length, type, radius, elevation, layer and motion tokens to utilities, with no competing colour value; `native/desktop/frontend/package.json, package-lock.json, vite.config.ts, components.json (new), src/theme.css (new), src/tokens.css, src/styles.css, src/lib/ (new)`.
- [x] `P02.S04` - Add the shared primitives from the official registry and adapt them to the shell tokens and density: button and icon button, input, label and field, dialog, popover, tooltip, tabs, segmented radio group, separator, scroll area, badge, keyboard hint, alert, progress and spinner, empty state, command, and the single icon registry over lucide-react; `native/desktop/frontend/src/components/ui/ (new), src/components/Icon.tsx`.
- [x] `P02.S05` - Set up the Storybook 10 catalogue on the application's own theme, strings and scheme switch, with stories covering each primitive's default, hover, focus, pressed, disabled, pending, error and success states, its static output under the build directory; `native/desktop/frontend/.storybook/ (new), src/components/ui/*.stories.tsx (new), package.json scripts, eslint.config.js, tsconfig.json`.

### Phase `P03` - sign-in dialog and password field

The first complete design: the sign-in dialog, its password field and the account controls, in every state the sign-in decision names.

- [x] `P03.S06` - Rebuild sign-in as a dialog with a password field that has an accessible label, a reveal control, password-manager and paste support, invalid, pending, throttled, runtime-unavailable and handover states, deliberate initial focus, dismissal and focus restoration, with the account controls restyled on the same primitives, the new chrome keys authored in four locales, stories for every state and the browser tests extended, keeping the submission rules of the sign-in state machine untouched; `native/desktop/frontend/src/components/SignIn.tsx, src/components/PasswordField.tsx (new), src/App.tsx sign-in composition, tests/desktop.spec.ts, dev/locales/desktop_chrome.py, src/cadrumo/locales/{en,es,ca,hu}/common.yml desktop subtree`.

### Phase `P04` - palette, settings, panes and feedback

The remaining shell surfaces rebuilt on the shared primitives with their hooks, keyboard operation and four locales intact.

- [x] `P04.S07` - Rebuild the command palette on the Command and Dialog primitives with grouped actions and documentation results, keyboard navigation, shortcut hints, loading, unavailable and empty states, keeping its documented hooks and the docs-search contract; `native/desktop/frontend/src/components/CommandPalette.tsx, its stories and tests`.
- [x] `P04.S08` - Rebuild settings on the Popover and segmented radio primitives with appearance, terminal colours, split, terminal text size, the display-language choice, account status and sign-out, and reset, keeping the appearance group first and its choice order; `native/desktop/frontend/src/components/Settings.tsx, src/shell/layout.ts, src/App.tsx language resolution, its stories and tests, locale keys`.
- [x] `P04.S09` - Rebuild the window and pane elements on shared primitives: rail with real tooltips, pane headers and icon buttons, panel tabs, split and panel separators with visible resize affordances, maximize and restore states, and the browser menu stand-in; `native/desktop/frontend/src/components/{Rail,PaneHeader,Split,ContextMenu}.tsx, src/App.tsx panel composition, their stories and tests`.
- [x] `P04.S10` - Unify supporting feedback: toasts, alerts and banners, progress, empty and error states, the terminal notes and the log view's tools, states and rows; `native/desktop/frontend/src/components/{RecordList,TerminalPane}.tsx, src/components/ui feedback primitives, src/App.tsx toast, their stories`.

### Phase `P05` - full-shell consistency and accessibility

The whole shell reviewed as one design across schemes, sizes, text scale and locales, with the findings fixed and the workflow documented.

- [x] `P05.S11` - Review the whole shell as one design in a browser across light and dark, small and large windows, 200 percent text, reduced motion and the four locales, check keyboard operation and focus visibility on every surface, and fix what the review finds; `native/desktop/frontend/src/, tests/`.
- [x] `P05.S12` - Remove superseded styles and components, complete the frontend README with the browser workflow, the catalogue, the scenarios, the stable hooks and the remaining native checks, update the native contract's desktop target table, and triage the latest packaged run finding by finding; `native/desktop/frontend/src/styles.css, native/desktop/frontend/README.md, native/CONTRACT.md desktop section`.

### Phase `P06` - focused native verification

The checks only the real Tauri window can answer, run where this session can run them and listed where it cannot.

- [x] `P06.S13` - Run the checks that need the real Tauri window where this session can, and record each remaining native integration check with its reason; `native/desktop/frontend/README.md native checks section`.

## Parallelization

Phases run in order: each builds on the tokens and primitives of the one before. Inside P04 the palette, settings and pane-element Steps touch different product components and may be prepared in parallel, but they share `src/App.tsx` and the theme stylesheet, so their edits to those two files are serialized. Review agents work read-only beside implementation and report at the Phase close. No other session writes under `native/desktop/frontend/`.

## Verification

- Every Step: `npm run check` (type check, lint, format) and the browser suite `npm test` pass under a configured build directory, and the changed surface is inspected in a browser in light and dark.
- P01: on a fresh build directory the documented bootstrap alone lets `npm run dev` start; the scenario entry renders each named scenario; editing a component updates the open page through hot reload; the production bundle contains no scenario code, proved by a test on the built output.
- P02: the theme stylesheet is the only place a role is mapped; a search finds no colour literal in `src/components/`; every primitive has stories for default, hover, focus, pressed, disabled, pending, error and success where the state applies; `storybook build` succeeds.
- P03: the browser suite's sign-in tests pass unchanged in intent: one submission, no retry, raw bytes with the token header, field cleared, secret absent from storage and the documentation frame; focus lands on the password field when the dialog opens and returns to its opener when it closes.
- P04: the palette, settings, pane and feedback surfaces keep every hook listed in the reference; keyboard operation is exercised for each; the four locales render without clipping at 520 px.
- P05: an accessibility pass (keyboard, focus visibility, roles, contrast, reduced motion) and a screenshot matrix (light and dark, small and large window, 200 percent text, four locales) are reviewed; the latest packaged run's findings are triaged one by one without editing a packaged assertion.
- P06: the checks that need the real window are listed with their outcome or the reason they could not run here.
- Plan close: all Steps closed, the final integrated review passes, `vaultspec-core vault check all` and `vaultspec-core vault plan check` are clean for this feature.
