---
tags:
  - '#audit'
  - '#desktop-design-system'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:c2c4647ccf25989de2f277202c58cfa4cbd0e7445979f7a77d7899226a340ad4'
related:
  - "[[2026-10-05-desktop-design-system-plan]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
---

# `desktop-design-system` audit: `phase checkpoint reviews`

## Scope

Rolling findings from the independent reviews run at each Phase close of `2026-10-05-desktop-design-system-plan`. Each entry names what was found, where, and how it was settled. No critical finding has been raised.

## Findings

### P01 bundle boundary | medium | the built-output check could not see three of the six development modules

`tests/bundle.spec.ts` searched for three literals that only two development modules carry, so a product import of the scenario list or the scenario control would have shipped unseen. Resolved in `3b361b991e`: the product build refuses any module under `src/dev/`, `dev/`, `.storybook/` or any story (`dev/product-boundary.ts`), the linter refuses the import (`eslint.config.js`), and the test holds the refusal to representative module ids. Proved by a deliberate import, which failed both the build and the linter.

### P01 gate freshness | medium | the check could inspect a stale build

A direct Playwright invocation skipped the npm lifecycle hook that built the bundle. Resolved in `3b361b991e`: the test run's own preview server command builds first (`playwright.config.ts`).

### P01 build input | medium | the single entry was a Vite default, not configuration

Resolved in `3b361b991e`: `vite.config.ts` declares `index.html` as the one input.

### P01 scenario coverage | medium | a refused sign-out and a mid-session terminal failure were unreachable

Resolved in `3b361b991e`: scenarios `sign-out-refused` and `session-failure`, a sign-in command that rejects, an unparsed log line and a dropped-records batch (`src/dev/scenarios.ts`, `src/dev/fixtures/`).

### P01 minor | low | fixture and documentation defects

Prototype keys in the fixture's asset lookup, an unreachable guard in the bootstrap, a single-project test command that could not start, three weak test assertions, index keys on a sliding list, no strict mode in the development entry, and a documentation origin that only knew two host names. All resolved in `3b361b991e`; the documentation fixture now listens on its own port, so it is another origin from any device.

### P02 pending focus | high | a pending submission disabled every control and dropped focus out of the dialog

With the field and both buttons disabled, focus fell to the document body and Tab reached controls behind the scrim. Resolved in `3692025e60`: a pending button reports `aria-busy` and `aria-disabled` and stays focusable (`src/components/ui/button.tsx`), the field is read-only while the answer is awaited, and the handover is guarded by the busy state on both surfaces (`src/components/SignIn.tsx`). A scenario test tabs during a pending submission and asserts focus stays in the dialog.

### P02 focus and failure colours | high | the focus ring and the failure colour were the same hue

The dialog opened with a ring that read as an error. Resolved in `3692025e60`: keyboard focus takes the ink role, the terracotta is kept for the chosen-item indicator, the invalid state no longer recolours the ring, and a field error carries an icon (`src/theme.css`, `src/components/ui/field.tsx`).

### P02 catalogue typefaces | high | the catalogue refused the shell's fonts, so every screenshot showed fallbacks

Resolved in `3692025e60`: the catalogue's server may read the documentation's static files (`.storybook/main.ts`), and the screenshot script fails on any failed font or refused response (`scripts/catalogue-shots.mjs`).

### P02 selection state | medium | hover, pressed and chosen shared one surface, and were near invisible in the dark scheme

Resolved in `3692025e60`: a `selected` role one step stronger than hover, a `raised` role for the chosen segment that is lighter than its track in the dark scheme, a brand bar on the chosen command row, and system highlight colours where colours are forced (`src/theme.css`, `src/components/ui/`).

### P02 contrast and type | medium | field outlines at 1.6 to one, pending text at 3.2 to one, Hungarian long vowels in fallback glyphs

Resolved in `3692025e60`: the field outline role reaches three to one, a pending button keeps full opacity, and the extended Latin faces are declared as the documentation declares them.

### P02 sign-in hierarchy and announcements | medium | the form stayed primary where a password could not help, and the throttle re-announced every second

Resolved in `3692025e60`: for a locked profile, an unavailable keyring or an unavailable runtime the form is not offered and the handover is the primary action; the throttle is announced once and its running number is visual only; the countdown timer runs only while a wait is owed (`src/shell/signIn.ts`); a failed sign-out has its own message.

### P02 touch targets | medium | 24 pixel controls with no coarse-pointer handling

Resolved in `3692025e60`: under a coarse main pointer every control grows one step through the density tokens (`src/tokens.css`), and splitter handles widen their hit area.

### P02 primitive API | low | naming differences between primitives

Alert takes `tone`, Badge and Button take `variant`, and form controls take `controlSize` because `size` is a native attribute. The Badge's outline variants now carry the alert's tone names. Left as is: Button keeps the registry's `destructive` name. Recommendation for a later pass: give Field a context that wires ids, error ids and the invalid state.

### P05 rail width | high | the rail had no width, so its chosen-item bar was drawn off the window

The grid column was `auto` and the `nav` carried no width, so the rail measured 36 pixels against a 48 pixel token and the bar computed to a negative offset. Resolved in `127fd9d1e7`: the rail takes `w-rail` and places its buttons by side padding (`src/components/Rail.tsx:79`). `tests/scenarios/keyboard.spec.ts` now measures the rail against its token and the bar against the window edge.

### P05 chords under a modal | high | global chords acted beneath the sign-in dialog

Settings opened under the scrim and took focus out of the modal. Resolved in `127fd9d1e7`: the chord handler stands down while the sign-in dialog or a menu is open, and under the palette lets through only the palette's own chord (`src/App.tsx`). A keyboard test presses four chords under the dialog and asserts none acted.

### P05 palette focus | high | an action run from the palette lost the focus it took

The palette closed, ran the action, and then returned focus to where it had been opened, so a terminal chosen by name was not focused and Settings opened from a terminal closed at once. Resolved in `127fd9d1e7`: the chosen action runs after the palette has closed and focus is back at its origin, as its chord would have run there (`src/components/CommandPalette.tsx`). Two keyboard tests cover a terminal chosen by Enter and Settings opened from inside a terminal.

### P05 log toolbar | high | the log's bar took the whole panel on a small or touch window

At 390 pixels with a coarse pointer the bar was 215 pixels of a 253 pixel panel. Resolved in `127fd9d1e7`: the bar is one row where there is room and two at most, the second scrolling sideways; the panel's floor rises under a coarse pointer (`src/tokens.css`); the window itself can no longer scroll (`src/theme.css`). Measured after: bar 107, list 97. A touch test in English and Hungarian holds the list's height and the window's stillness.

### P05 log rows | high | record actions were pointer-only and no row showed as current

Resolved in `127fd9d1e7`: records are one tab stop with arrow, Home and End movement, Enter opens a record's detail, the menu key opens the menu a right-click opens under its row, and the current row carries an ink bar and the hover wash (`src/components/RecordList.tsx`). Not done: a registry action for copying the visible records, which would need the filtered list lifted out of the log view; the menu is now reachable by keyboard, which was the gap.

### P05 palette listbox | high | status text inside the listbox failed the rule engine when nothing matched

Resolved in `127fd9d1e7`: what the list cannot show as rows is said beside it, outside the listbox, and an empty group is not rendered. The audit now covers the palette with every action and with nothing found.

### P05 state surfaces | medium | hover and highlight were near invisible on chrome and in menus

Hover measured 1.06 to one on chrome. Resolved in `127fd9d1e7`: hover and the chosen surface are washes of ink over whatever they sit on (`src/theme.css`), menu items take the chosen-row surface and bar, and a keycap is outlined instead of filled. Faint text has no contrast to spare for a tinted surface in either scheme, so a current log row keeps the lighter wash and its time is in the secondary text colour.

### P05 follow | medium | following the log lost its end where rows wrapped

Found while settling the toolbar: off-screen rows were sized by estimate, so the first scroll to the end fell short on a narrow panel and the view stopped following. Resolved in `127fd9d1e7`: the estimate is gone, which the 400-row window had made redundant, and following is held through a resize of the list. Paging to earlier records restores the scroll position itself instead of relying on scroll anchoring, and the window shrinks back at the newest record or on a filter change.

### P05 purity and hot paths | medium | an impure state updater, and work repeated on every pointer move

The dropped-record count was set inside another updater and doubled under strict mode. A dragged splitter rebuilt the action registry, recounted errors and wrote storage on each move. Resolved in `127fd9d1e7`: one state for the ring and its losses, narrowed dependencies, a memoised count and log view, and a debounced save flushed on page hide (`src/App.tsx`).

### P05 reach | medium | no keyboard way out of a terminal, and actions missing from the palette

Resolved in `127fd9d1e7`: F6 and Shift+F6 move between the documentation, the TUI, the bottom panel and the rail; signing in and out are actions; the untyped palette lists every action; a view chosen by name is shown, not toggled. Not done: grouping actions under headings, which needs a string for each group.

### P05 touch | medium | controls under a fingertip

Resolved in `127fd9d1e7`: every density step is at least 2.75rem under a coarse pointer, the splitter's hit area is 45 pixels, palette rows take the density tokens, the palette's Esc keycap is its close button, and a record's detail toggle is a button of the smallest control size. The touch test's floor is 44 pixels in both dimensions and covers the log's bar.

### P05 names and roles | medium | assistive names that misdescribed

Resolved in `127fd9d1e7`: the TUI's named frame is a group, the palette and settings openers report `aria-expanded`, the Logs tab says its error count in words, the menu has a name, and a failed environment read no longer says the part needs the desktop application. A segmented control now checks the segment keyboard focus arrives on without depending on the key still being held, which a key sent by software may not be.

### P05 tooltip layer | medium | a tooltip on its way out took the Escape meant for the dialog beneath

Found by the content security policy test added at this checkpoint. Resolved in `56b74d1b86`: a tooltip arrives by a transition from its starting style and unmounts at once (`src/components/ui/tooltip.tsx`).

### P05 build output | medium | the product build never emptied its output directory

Found by the benchmark once it counted the whole build: ten megabytes of earlier builds' files sat in the directory the desktop package embeds. Resolved in `6a9b5a200c`: the build empties it and the bundle test reads every file there.

### P05 measurement | medium | benchmark numbers that did not measure what they named

Resolved in `6a9b5a200c`: whole-build sizes, in-page terminal timing, a drag of one move to a frame that is checked to have moved, a filter timed before paging, an overlay churn check for accumulation, and budgets enforced by `--check` (`scripts/benchmark.mjs`).

### P05 accepted | low | left as they are

The palette, settings and the menu unmount when they close, so they leave at once while the sign-in dialog fades; the difference is deliberate, since each captures where focus came from when it mounts. Popper offsets are pixel numbers the foundation takes as props. The record menu's rule-engine audit leaves out the landmark rule, because a context menu is drawn at the pointer outside any landmark, as the native menu it stands in for is.

## Recommendations

- From `P02 primitive API`: give Field a context that wires ids, error ids and the invalid state, so a form control cannot be mislabelled by hand.
- From `P05 reach`: decide whether the palette groups its actions under headings; it needs one chrome string per group in four languages, which is a new string family for the user to authorize.
- From `P05 log rows`: if copying the visible records should be an action as well as a menu item, lift the filtered list out of the log view first.
- From `P05 follow`: check the log in a WebKit webview, which has no scroll anchoring, while records arrive and the view is not following.
- From `P05 names and roles` and the sign-in findings: rerun the packaged acceptance suite on a built package; nothing in these reviews exercised the Tauri host.
