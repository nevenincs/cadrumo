---
tags:
  - '#audit'
  - '#desktop-design-system'
date: '2026-10-05'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:04ec968c9f52baed42c9a382da818b2803e95bce888af531720613eb3dda13c5'
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

### Final review focus | high | a view chosen in the palette from a terminal or the documentation often did not get focus

The re-review of the P05 fixes measured it: opened in the console terminal, the palette's Python shell was focused five times in eight; a chord pressed inside the documentation frame, none in eight. The view is shown by a state change that commits after the request, and the focus call ran while its pane was still hidden. Resolved in `ce5a6efd14`: focus is a wish held in a ref and granted after the commit that shows the view, or dropped after a second (`src/App.tsx`, `grantFocus`). Two keyboard tests repeat the terminal and the documentation paths.

### Final review guard | medium | the chord guard counted a dialog that was not on screen, and one entry skipped it

Chords were dead while the sign-in state was still being read, and chords forwarded by the documentation's bridge acted under the open dialog. Resolved in `ce5a6efd14`: the guard requires an answered status, and the key listener and the bridge pass through the same function. F6 skips an area that has nothing to focus.

### Final review menu | medium | the shell's own menu took focus back from a press outside it

Made non-modal in the P05 fixes, it still refocused its origin on every close, so a click on the filter lost its focus and a right-click on another record opened no menu. Resolved in `ce5a6efd14`: a close caused by a press elsewhere leaves focus there; a menu opened by the menu key is anchored to its row's edge and no longer covers it.

### Final review log | medium | the log was not one tab stop, and a short panel made it a second scroller

Every record's detail toggle was tabbable, and the short-window fix of `e33436de3d` let the whole view scroll, which hid the newest record in the smallest window. Resolved in `ce5a6efd14`: the toggle is reached from its row; a panel near its floor gives the bar one row through a height query on the panel, and only the list scrolls. Bringing in earlier records now holds the view on the record at its top, and a focused record that leaves the drawn span hands focus to the oldest one drawn.

### Final review minor | low | contrast, touch sizes and statements

Shortcut text on a highlighted menu item, the narrow tab and the palette's close control under a fingertip, and three README sentences that did not match the code. Resolved in `ce5a6efd14`. Left: the Hungarian level select cuts one letter at its narrowest, and the log bar's sideways scroll has no visible cue.

### Final review results directory | medium | the browser tests emptied the directory other results are written to

Found when a benchmark result vanished: Playwright empties its output directory at each start, and that was the directory the benchmark, the catalogue screenshots and the packaged run write into. Resolved in `ce5a6efd14`: the browser tests have their own subdirectory.

### Confirmation follow | high | the log stopped following by itself while records arrived

Found by the scenario page's live feed, added to test the confirmation pass's findings: with a batch every 30 to 40 milliseconds the drawn span grew past its window with no interaction. The view was moved to the end in a passive effect, and a scroll reported between the commit and that effect saw an end that had moved on. Resolved in `f3ec3897b9`: the view moves in the commit that draws the records, and following ends only on an upward scroll (`src/components/RecordList.tsx`).

### Confirmation menu key | high | the real menu key still laid the menu across its row

The confirmation pass pressed the key 48 times and the menu was clear of its row in none: Chromium reports the key as a mouse event with no button, which the test's synthetic event did not reproduce. Resolved in `f3ec3897b9`: `src/shell/pointer.ts` tells the two apart for the log and the terminals, and the keyboard test presses the key at the end, the middle and the top of the list.

### Confirmation short bar | high | the level select collapsed in the one-row bar

In a panel near its floor the select's wrapper shrank to nothing and lay under its neighbours. Resolved in `f3ec3897b9`: each control of the row keeps its width; a test at the smallest window holds every control's width and order.

### Confirmation reader's place | medium | arriving records moved the view of a reader who had left the end

The drawn span slid with the newest record, so a reader resting high in a large span lost their place, and a focused record that left the span sent focus hopping from record to record. Resolved in `f3ec3897b9`: off the end the span is pinned to its first record and grows; a focused record that leaves hands focus to the list once; a press outside the log clears the memory of where focus was. Two tests run against the live feed.

### Confirmation minor | low | focus after a press in the documentation, after signing in with the TUI hidden, and from a detail toggle

Resolved in `f3ec3897b9`. A pending focus wish is dropped on the next press, which the confirmation pass measured at 0 of 24 overridden with the guard and 22 of 24 without. Left: with an unreadable source and records together in a panel at its floor, the banner leaves the list less than one row.

### Log check span | medium | a reader off the end was eventually given the whole log to draw

An independent check of `f3ec3897b9` measured the pinned span growing to the ring's ten thousand records, with frames of 50 milliseconds and more under a feed in the development build. Resolved in `17c72f803c`: the span holds at most five windows and moves a window at a time as the reader nears either end; the view is put back on the record at its top whenever what is drawn changes, which also covers the ring dropping records in an engine without scroll anchoring. The benchmark's new stage reads a full log streaming at the host's maximum: two thousand rows drawn, frames at 16.7 milliseconds median and 16.8 at the ninety-fifth percentile in the production build.

### Log check leaving and returning | medium | a slow scroll never ended following, and End did not always resume it

Upward movement was measured from the previous scroll, so a pixel at a time never counted, and under a feed a gentle wheel was undone by the next batch; End relied on a scroll report that a batch could overtake, failing 3 times in 64. Resolved in `17c72f803c`: movement adds up from the end, an upward wheel or a downward finger leaves the end at once, End asks for the end outright, and an opened detail at the end keeps the newest record in view. Five tests run against the live feed.

### Log check left | low | what the check could not settle

Whether the menu key is told from a pointer in engines other than Chromium, which Playwright's WebKit and Firefox do not let a test press; and returning to the end of a log growing at the host's maximum by ordinary wheel notches, which loses the race, where End and the Follow button are the way back.

### Account review offers | medium | a locked profile was still offered a password in three places

An independent review of `17fec7e798` and `09f8ce4c89` found the dialog withholding the password field for `PROFILE_LOCKED` while the TUI pane, settings and the palette still offered sign-in. Resolved in `3ba984d705`: whether a password can settle the account is one answer from the controller, at `native/desktop/frontend/src/shell/signIn.ts:88`, read by every element; the pane shows the refusal in place of its lead. The account-state table test gained a locked-profile row.

### Account review focus | medium | choosing the TUI's own flow left the keyboard on nothing

From the pane, settings or the palette, "Set up a profile" and "Open the TUI" started the TUI and left focus on the document body. Resolved in `3ba984d705`: one handler shows the TUI and asks for focus there, and a focus wish is kept for its short life so a view that is rebuilt as it starts is given focus again. Settings returns focus to its opener only when nothing else has taken it. Three tests cover the three ways in.

### Account review wording | medium | with no services running the dialog and settings said something else

The dialog was titled as a sign-in over a generic lead, and settings named a profile it could not know. Resolved in `3ba984d705`: the dialog's title is the phase's own words and the profile section is left out where the profile is not known. Two existing assertions on the refusal sentence now assert the dialog's heading instead, which is the same fact in the words the rest of the window uses.

### Account review minor | low | settled in the same change

A refusal the person had seen came back when its surface was reopened, and a failed sign-out stayed in settings; a running wait and a locked profile are kept because they are still true. The first Escape in a dialog closed only a tooltip open over it. A failed sign-out left the dialog suppressed for the next time the gate closed. The window section of settings was not a labelled region, a stray rule showed where there was no account, the header said nothing while the status was being read, the address test matched a key in any table, and hidden scrollbars relied on one engine's property.

### Calendar page | medium | the filing calendar was a component nothing could open

Resolved in `c536509aed`: profile views are an optional part of the host port at `native/desktop/frontend/src/shell/host.ts:62`. The desktop host offers none, so the product shows no button, action or page; the scenario host offers the calendar from a fixture, as design evidence only. The page is read when shown, dropped at sign-out, and a failed read is never drawn as an empty calendar. The audit engine found the month headings skipping a level, which was corrected. No row links to a Modelo: the window cannot take the TUI to a page.

### Messages button | medium | the product's latest-notifications read carries no unread count

Resolved for the window in `2905b2e711` and `5273a9949a`: the rail's Messages button shows what was unread at the last capture and opens the TUI. `app live notifications latest` reports a capture time and a row count only; whether a row was read is on rows that carry names and tax numbers, so the view's type at `native/desktop/frontend/src/shell/views.ts:79` is counts only and no row reaches the window. Never captured and a failed read carry a hollow pin and say which in the name and tooltip, so neither is read as none unread. No host provides the view yet.

### Views review scroll | high | the focused calendar page could not be scrolled by keyboard

An independent review of `3ba984d705` and `c536509aed` measured Page Down, the arrows, Space and End leaving the page where it was: focus sat on a wrapper around the element that scrolls. Resolved in `03c4d21dd0`: the page is one region that scrolls and holds focus, at `native/desktop/frontend/src/components/FilingCalendar.tsx:372`. A test presses Page Down and Home in a short window.

### Views review account | medium | the calendar and the account disagreed outside the signed-in phase

Withheld, the page said "Sign in" in every phase, including a locked profile, no services, and a platform that signs in inside the TUI, where it then never read. What it had read was kept by a yes or no rather than by profile. Resolved in `03c4d21dd0`: the page says the phase's own words and offers a sign-in only where one can be given; where sign-in is the TUI's it asks and shows the answer; reads are keyed to the profile, and a refused read has the account's status read again. The account-state table test now opens the calendar in each state.

### Views review dead end | medium | a locked profile had no way on in settings or the palette

Settings showed a badge and nothing else, the palette listed no account action, and the dialog was titled as a sign-in with no field. Resolved in `03c4d21dd0`: settings shows the refusal and offers the TUI, the palette has the same action wherever the account is not settled, and the dialog is titled in the phase's words.

### Views review focus | medium | focus fell to the document in five places

After refreshing a failed read; after signing out with focus in the page; after putting the sign-in dialog aside when it was opened from the calendar with the TUI hidden; when the calendar was chosen while the TUI was maximized; and a refused password took focus back from wherever the person had moved it. Resolved in `03c4d21dd0`: the failed view keeps its button through a new read, the page takes focus that its own controls lose, the dialog returns focus to what asked for it, the calendar takes focus once it is laid out, and a refusal refocuses the field only from the form. Putting the calendar away from the rail leaves focus on the rail.

### Views review settle | medium | a failed sign-out came back unless settings was closed with Escape

Only one of the three ways settings closes cleared it. Resolved in `03c4d21dd0`: it is cleared whenever settings is no longer open; the test closes it two ways.

### Views review minor | low | settled in the same change

The distance to a deadline was hidden in a pane under 448 pixels, which is every phone and a common side-by-side width; it now moves under the row's notes. The documentation's zoom and history acted on a hidden page while the calendar was shown, and the header's maximize was named for the documentation. Rows took a hover surface while leading nowhere. The header's way back shared an icon with the rail's documentation home; it is now the pane's close, as the TUI's is. Six tests that asserted less than their names said were tightened.

### Views review left | low | not reproduced

One run of the full suite failed a test at its first step, the sign-in dialog not appearing in the no-profile scenario; it passed in eighteen repeats and two further full runs. Recorded as seen once under load, not as fixed.

### Calendar head | low | the calendar opened on a list to be read row by row

Settled in `87ccfcf7bb` and `240b778d69`: the page's head counts the range in the product's four readings, the pressing ones first, without combining them; a deadline more than two months ahead is said in months while lateness stays in the product's own days; Ctrl+Shift+D shows the calendar and puts it away.

### Third review ways on | medium | withheld, the calendar and Messages fell short of the pane beside them

An independent review of `2905b2e711`, `5273a9949a` and `03c4d21dd0` found no high defect. Withheld, the calendar named the phase and dropped the refusal and every way on; carrying on in the TUI left it a dead end until the window was refocused; Messages did nothing at all while the TUI was withheld. Resolved in `02f69e0f28`: the calendar shows what the TUI pane shows by the same component at `native/desktop/frontend/src/components/SignIn.tsx:400`; in the TUI's own flow it reads the account's status once on opening and offers to read it again; Messages leads to the pane's way in. The account-state table test checks the calendar's offers and what Messages says in every state.

### Third review focus | medium | the dialog's way to the TUI left the keyboard where the dialog was opened from

Opened from the calendar or the palette, "Open the TUI" and a successful sign-in returned focus to the opener while the TUI started. Resolved in `02f69e0f28`: put aside, the dialog returns focus to what it took it from, including when the gate closing opened it; admitted, focus goes on to the calendar that asked or to the TUI. Signing out from a focused terminal leaves focus on the pane's way back in.

### Third review not known | low | no answer yet was drawn as none unread

For as long as the read took, and whenever the account withheld it, Messages showed nothing, as it does for none unread; under a finger the pin's meaning could not be reached. Resolved in `02f69e0f28`: both carry the hollow pin, the withheld one with the account's reason; a tap says in a toast why there is no count. The pin is centred where a count is and no longer paints a disc on a hovered button. A second failed read is announced by a new alert while its button stays and keeps focus.

### Third review tests | low | three tests asserted less than they claimed

Status reads were compared with a number already reached before the step under test; a page was "scrolled by a finger" through a script call; a saved value was read before the save had run. Each now asserts what it names.

### Third review left | low | one fix has no test of its own

Returning focus to the calendar after a dialog opened by a session ending underneath is fixed by the same code that a pressed opener uses, but no test ends a session from outside: the scenario host has no handle for it.

### Shell upkeep | low | found while measuring, settled as found

The development server reloaded the whole page on every save of the sign-in and log components, because each module exported values beside its components; they have modules of their own since `3d1ee577dd`. In Spanish and Catalan a phone-width window cut the calendar's pane title, measured as 176 pixels in 148; a narrow header now gives up the split's controls, which the TUI's header keeps (`8eda21e211`). A bar that scrolls sideways with its scrollbar hidden showed nothing of what lay beyond; it fades at the edge with more, by a utility in the theme (`ed1c4476c8`). Eighty toggles of the calendar grew neither nodes nor listeners but made a read each; a calendar read within half a minute is shown again as it is (`73767c6a4a`). A probe over all seventeen scenarios with every rail button, the palette, F6 and the calendar's chord logged no console error or warning.

### Fourth review dead end | medium | carrying on in the TUI could not be left when the TUI could not start

An independent review of `87ccfcf7bb` to `3d1ee577dd` found no high defect. With a session that fails to start, "Open the TUI" left the window continuing in the TUI for good: no sign-in was offered in the pane, the calendar, settings or the palette. Resolved in `8fd9537360`: a session that fails to start ends that state as one that exits does, and the reason is said. The scenario `tui-unavailable` and a test hold it.

### Fourth review focus | medium | three more places focus was lost or taken

A sign-in that succeeded after its dialog was put aside left focus on the document. Putting the calendar away with no documentation behind it did the same. The dialog's close, which runs when its exit has finished, took focus back from wherever the person had put it meanwhile. Resolved in `8fd9537360`; the first fix at first also moved focus into the terminal at startup, which the palette's own test caught before it was committed.

### Fourth review minor | low | settled in the same change

A far deadline rounded to the nearest month read as further off than it is: it is now whole months that have fully to pass, with the rule at `native/desktop/frontend/src/shell/calendar.ts:42` and a test at its boundaries. A calendar shown again after a failed read said the old failure and then the new one. The head's counts were one unlabelled paragraph. The documentation's bridge ran an action without asking whether it was offered. A gate drawn in two panes announced its refusal twice. A control disabled in name looked enabled. Looking at the account again showed nothing while it ran. Five tests asserted less than their names and were tightened; the bridge's refusal on a host without views has no test, because nothing observable differs.

### Log review place | high | a reader of the log lost their place in two ways

The first independent check of the log view since `17c72f803c`. A filter change left the old view's scroll anchor behind: with five thousand records, scrolled up three thousand pixels, a filter typed and cleared, and a two-pixel scroll, the view landed three thousand pixels from the end. And with no current record drawn the tab stop was the last drawn row, so Tab into the list threw a reader who had scrolled to the far end of the span; after the ring dropped a focused record an arrow key jumped thirty-four thousand pixels. Resolved in `543709e5d3`: the place is taken at once whenever the end is left and dropped whenever it is returned to; a filter that still shows the reader's record keeps their place and one that hides it starts at the end; a reader who has left the end tabs onto the list itself, and an arrow goes to the record at the top of their view. Four tests reproduce the measured cases.

### Log review keyboard | medium | keys that moved the view without the reader, or the reader without the view

Page Up and Page Down scrolled without moving the current record, so the next arrow snapped back. An arrow up from the newest record did not stop following when its target was in view. A jump by Home was undone when a batch committed before the scroll was reported, in three trials of four. Home reached only the top of the drawn span, eleven presses from the end of five thousand records. "Clear log filters" and the logger chip left focus on the document. Resolved in `543709e5d3`, each with a test.

### Log review minor | low | settled in the same change

The notice of dropped records stood above every span, with thousands of older records still above it. A fast scroll hit the edge of the drawn span before the next came in. A sideways wheel with a pixel of upward jitter stopped following. A host record printed its source twice and said a warning by colour alone. The log had no name. The keyboard's menu was offset by the row's height. Under a finger at 390 by 844 the bar stayed two rows and left the records ninety-seven pixels; it is one row there now. Five of the tests the check named were tightened, and a touch drag now has a test.

### Log review left | low | not changed

Rows have no role of their own beneath the log. Three tests still rest on a fixed wait: the gentlest wheel, the cap on the drawn span, and focus handed to the list once. The frame times and heap the check measured are of the development build; the production figures are the benchmark's, which stayed within budget after the change.

### Overlay focus | medium | settings could be left open with the keyboard outside it

Found when the benchmark, moved to the canonical build directory, failed one run in three in its overlay stage. With a tooltip showing anywhere in the window, Escape pressed inside settings closed only the tooltip; a test that hovers a rail button with focus in settings fails without the fix. And the palette, a moment after it had gone, took focus back to its opener even when another surface had opened and taken focus in that moment. Resolved in `bc428c15e3`: the popover closes at the first Escape as the dialog does, at `native/desktop/frontend/src/components/ui/popover.tsx:43`, and the palette leaves focus where it has been put. The benchmark passed three runs in three afterwards; it also waits for settings to hold focus before pressing a key in it.

## Recommendations

- From `P02 primitive API`: give Field a context that wires ids, error ids and the invalid state, so a form control cannot be mislabelled by hand.
- From `P05 reach`: decide whether the palette groups its actions under headings; it needs one chrome string per group in four languages, which is a new string family for the user to authorize.
- From `P05 log rows`: if copying the visible records should be an action as well as a menu item, lift the filtered list out of the log view first.
- From `P05 follow`: check the log in a WebKit webview, which has no scroll anchoring, while records arrive and the view is not following.
- From `P05 names and roles` and the sign-in findings: rerun the packaged acceptance suite on a built package; nothing in these reviews exercised the Tauri host.
- From `Calendar page`: the page reaches a real profile only once a host command exists; that waits on the proposed decision `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr`.
- From `Calendar page`: a row's link to its Modelo needs a decision on how the window asks the TUI for a destination.
- From `Messages button`: decide whether the host counts unread rows or the product gains a summary read; either keeps the rows out of the window.
