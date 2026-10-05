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
body_hash: 'sha256:27588911e48063dc076ee15964b2554499df2b1c19d3d3705874d0826c2c75cf'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace desktop-design-system with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `desktop-design-system` plan

<!-- One-line headline summary plan. -->

## Description

<!-- First line after approval: `Approved yyyy-mm-dd`, written by the
orchestrator after establishing scoped authorization, including an explicit
advance authorization. Record its basis; ask only when it is absent. Then briefly describe the proposed work.
Reference `{adr}`s, `{research}`, `{reference}`. Supporting documentation
must be read when relevant. State the decision coverage assessment; when no
costly decision is involved and no ADR governs, say so. With several ADRs,
map their scope to Steps at L1 or the relevant containers at higher tiers. -->

## Steps

### Phase `P01` - browser development loop

A fresh checkout reaches a hot-reloading shell in a browser with selectable host scenarios, and the product build contains none of the scenario code.

- [ ] `P01.S01` - Document and prove the lightweight bootstrap that configures the standalone desktop project and runs the existing chrome-string and palette generators, so the development server starts on a fresh build directory without Rust, a wheel or a documentation build, and record the browser development commands; `native/desktop/frontend/README.md (new), native/desktop/frontend/package.json scripts`.
- [ ] `P01.S02` - Add the development-only scenario host implementing Host with deterministic signed-out, signing-in, signed-in, wrong-password, throttled, runtime-unavailable, loading, empty and error scenarios, mounted from a separate development entry page with a labelled scenario switcher, a deterministic terminal fixture and a separate-origin documentation fixture, and prove by a test on the built output that the production bundle contains none of it; `native/desktop/frontend/scenarios.html (new), native/desktop/frontend/src/dev/ (new), native/desktop/frontend/vite.config.ts, native/desktop/frontend/tests/`.

### Phase `P02` - tokens, primitives and catalogue

One theme bound to the generated palette, the shared primitives every surface composes, and a Storybook catalogue of their states.

- [ ] `P02.S03` - Add the pinned design-system dependencies and the Tailwind 4 integration, and reconcile the stylesheets into one theme that maps the generated palette to semantic roles on every scheme boundary and exposes the length, type, radius, elevation, layer and motion tokens to utilities, with no competing colour value; `native/desktop/frontend/package.json, package-lock.json, vite.config.ts, components.json (new), src/theme.css (new), src/tokens.css, src/styles.css, src/lib/ (new)`.
- [ ] `P02.S04` - Add the shared primitives from the official registry and adapt them to the shell tokens and density: button and icon button, input, label and field, dialog, popover, tooltip, tabs, segmented radio group, separator, scroll area, badge, keyboard hint, alert, progress and spinner, empty state, command, and the single icon registry over lucide-react; `native/desktop/frontend/src/components/ui/ (new), src/components/Icon.tsx`.
- [ ] `P02.S05` - Set up the Storybook 10 catalogue on the application's own theme, strings and scheme switch, with stories covering each primitive's default, hover, focus, pressed, disabled, pending, error and success states, its static output under the build directory; `native/desktop/frontend/.storybook/ (new), src/components/ui/*.stories.tsx (new), package.json scripts, eslint.config.js, tsconfig.json`.

### Phase `P03` - sign-in dialog and password field

The first complete design: the sign-in dialog, its password field and the account controls, in every state the sign-in decision names.

- [ ] `P03.S06` - Rebuild sign-in as a dialog with a password field that has an accessible label, a reveal control, password-manager and paste support, invalid, pending, throttled, runtime-unavailable and handover states, deliberate initial focus, dismissal and focus restoration, with the account controls restyled on the same primitives, the new chrome keys authored in four locales, stories for every state and the browser tests extended, keeping the submission rules of the sign-in state machine untouched; `native/desktop/frontend/src/components/SignIn.tsx, src/components/PasswordField.tsx (new), src/App.tsx sign-in composition, tests/desktop.spec.ts, dev/locales/desktop_chrome.py, src/cadrumo/locales/{en,es,ca,hu}/common.yml desktop subtree`.

### Phase `P04` - palette, settings, panes and feedback

The remaining shell surfaces rebuilt on the shared primitives with their hooks, keyboard operation and four locales intact.

- [ ] `P04.S07` - Rebuild the command palette on the Command and Dialog primitives with grouped actions and documentation results, keyboard navigation, shortcut hints, loading, unavailable and empty states, keeping its documented hooks and the docs-search contract; `native/desktop/frontend/src/components/CommandPalette.tsx, its stories and tests`.
- [ ] `P04.S08` - Rebuild settings on the Popover and segmented radio primitives with appearance, terminal colours, split, terminal text size, the display-language choice, account status and sign-out, and reset, keeping the appearance group first and its choice order; `native/desktop/frontend/src/components/Settings.tsx, src/shell/layout.ts, src/App.tsx language resolution, its stories and tests, locale keys`.
- [ ] `P04.S09` - Rebuild the window and pane elements on shared primitives: rail with real tooltips, pane headers and icon buttons, panel tabs, split and panel separators with visible resize affordances, maximize and restore states, and the browser menu stand-in; `native/desktop/frontend/src/components/{Rail,PaneHeader,Split,ContextMenu}.tsx, src/App.tsx panel composition, their stories and tests`.
- [ ] `P04.S10` - Unify supporting feedback: toasts, alerts and banners, progress, empty and error states, the terminal notes and the log view's tools, states and rows; `native/desktop/frontend/src/components/{RecordList,TerminalPane}.tsx, src/components/ui feedback primitives, src/App.tsx toast, their stories`.

### Phase `P05` - full-shell consistency and accessibility

The whole shell reviewed as one design across schemes, sizes, text scale and locales, with the findings fixed and the workflow documented.

- [ ] `P05.S11` - Review the whole shell as one design in a browser across light and dark, small and large windows, 200 percent text, reduced motion and the four locales, check keyboard operation and focus visibility on every surface, and fix what the review finds; `native/desktop/frontend/src/, tests/`.
- [ ] `P05.S12` - Remove superseded styles and components, complete the frontend README with the browser workflow, the catalogue, the scenarios, the stable hooks and the remaining native checks, update the native contract's desktop target table, and triage the latest packaged run finding by finding; `native/desktop/frontend/src/styles.css, native/desktop/frontend/README.md, native/CONTRACT.md desktop section`.

### Phase `P06` - focused native verification

The checks only the real Tauri window can answer, run where this session can run them and listed where it cannot.

- [ ] `P06.S13` - Run the checks that need the real Tauri window where this session can, and record each remaining native integration check with its reason; `native/desktop/frontend/README.md native checks section`.

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

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     For user-requested coordination across the program and its tracker,
     vaultspec-projectmanager owns that context and assignments; this
     plan remains the home of implementation sequencing.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step is closed (`- [x]`) and the final
cohesive review passes. At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

Review follows the vaultspec system section. L1 has no Phase close;
coincident plan-close and handoff gates share one integrated review. -->

## Context

Rebuild the desktop shell's presentation on one design system (shadcn/ui on Radix, Tailwind 4, Storybook 10) developed in a browser against deterministic host scenarios.

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
