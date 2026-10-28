# Cadrumo desktop shell frontend

The React shell of the Cadrumo desktop window. It is developed in a browser:
the same components that run inside the Tauri window run on a Vite development
server, against a simulated host, with hot reload. Compiling the desktop host,
assembling a package or building the documentation is not needed to edit it.

From the repository root, run `just dev`. It generates the shell's inputs in
the host preset's repository build, `build/<preset>`, and starts the development
display from that build at `http://localhost:15370/scenarios.html`.
The fixed listener assignments live in `../development-server.json`: display
15370, product preview 15371, documentation fixture 15372, and Storybook 6006,
and for the browser tests the scenario preview 15373, its documentation
fixture 15374 and the hot-reload server 15375. The tests have ports of their
own, so `just dev` can stay open while they run. An occupied port is an error;
no server moves to another port.

The packaged app's Logs tab starts at INFO. Set `CADRUMO_LOG_LEVEL` to `DEBUG`,
`INFO`, `WARNING`, `ERROR`, or `CRITICAL` before launching it to select another
initial level. The level selector changes the current view; Reset filters restores
the environment-selected level. Internal stages and successful helper timings are
DEBUG, operational state changes are INFO, recoverable degradation is WARNING,
and failed operations are ERROR. Diagnostic files retain DEBUG by default;
`CADRUMO_LOG_FILE_LEVEL` and `CADRUMO_LOG_ROOT_LEVEL` govern Python capture separately.

## Prerequisites

- Node.js and npm, with dependencies installed by `npm ci` in this directory.
- CMake 4.4 or newer.
- The repository's development Python environment, which the generators run in.

## The build directory

The frontend has no build directory of its own. Every development, check,
build and test path reads the repository build under test, `build/<preset>`
(`build/windows-x64` on Windows), configured once at the repository root with
`cmake --preset <preset>`. The development server reads the build paths, the
product identity and the server address from it. The shell reads two more from
its `desktop/frontend-generated/`: the chrome strings, projected from the locale
catalogues, and the palette, projected from the documentation theme. Nothing
generated is written into the source tree.

The `desktop-frontend-generated` target writes those two and regenerates them
when a locale catalogue or the documentation theme changes. It compiles
nothing. `desktop-frontend-dev` (what `just dev` builds), `desktop-frontend-build`
and `desktop-frontend-test` depend on it; `npm run dev` only reads the build and
never configures or builds it.

The servers bind the address in `../development-server.json`. Another address
is a configure option of the repository build, for example
`cmake --preset windows-x64 -DCADRUMO_DESKTOP_BIND_ADDRESS=127.0.0.1`. Ports
cannot be overridden.

The CMake targets set the build directory for the commands they run. Running
an npm script directly needs it named in the environment:

```sh
# PowerShell
$env:CADRUMO_CMAKE_BINARY_DIR = '<absolute path to the build directory>'
# POSIX shell
export CADRUMO_CMAKE_BINARY_DIR='<absolute path to the build directory>'
```

## Develop in a browser

```sh
just dev
```

The server offers three pages.

- `/` is the production entry. Without a desktop host it uses the browser host,
  which fabricates nothing: every backend capability reports itself
  unavailable.
- `/scenarios.html` is the development entry. It mounts the same application on
  the scenario host and shows a **Simulated host** control in the bottom
  corner for switching scenario and language.
- `/primitives.html` mounts one primitive over made-up rows, for the browser
  tests: the data grid (`?rows=10000`, `&grouped` for month sections) or the
  plain table (`?harness=table`), or the sheet and filter chips
  (`?harness=companions`), in either scheme (`&scheme=dark`).

Edit a component and the open page updates in place.

### Scenarios

A scenario is a named, deterministic host behaviour, declared as data in
`src/dev/scenarios.ts`.

| Scenario              | What it presents                                                         |
| --------------------- | ------------------------------------------------------------------------ |
| `signed-out`          | No live sign-in; any password is accepted after a fixed delay            |
| `signing-in`          | A submission the host never answers, so the pending state stays up       |
| `signed-in`           | A live sign-in; the TUI pane runs its fixture session                    |
| `wrong-password`      | Every submission refused with `CREDENTIAL_REJECTED`                      |
| `throttled`           | Every submission refused with `THROTTLED` and a 30 second wait           |
| `profile-locked`      | Status carrying `PROFILE_LOCKED`, which hands over to the TUI            |
| `no-profile`          | No active profile: nothing to sign in to, so the TUI's setup is offered  |
| `runtime-unavailable` | Unknown presence with no runtime to ask                                  |
| `unsupported`         | A platform without sign-in: no sign-in view, no Account section          |
| `loading`             | An environment, status, log subscription and sessions that never answer  |
| `empty`               | Signed in with no log records, silent sessions and no search results     |
| `error`               | Refused environment and status reads, an unreadable log, failed sessions |
| `logs-missing`        | A log source that reports missing, which is not an empty log             |
| `sign-out-refused`    | Signed in, with a sign-out command that fails                            |
| `session-failure`     | Sessions that start, print a line, then fail and exit                    |
| `tui-unavailable`     | Signed out, with sessions that cannot start: the TUI is not a way on     |
| `views-refused`       | Signed in, with every profile view refused: not an empty calendar        |
| `ledger`              | Signed in with a 2026 ledger and earlier years; 2026 1T is sealed        |
| `no-views`            | Signed in on a host with no profile views                                |

Every scenario but `no-views` offers the profile views (the filing calendar
and the notification counts behind the Messages button) from a fixture;
`empty` offers a calendar with nothing due and notifications never captured.
The same scenarios offer the ledger port from a made-up ledger held in the
page's memory, which answers with the registered contracts' rules: the list's
filter, sort, group and page order, ids that change with a movement's amount,
description, date or account, refusals for sealed rows, idempotent adds, and
a model review answered only with the digest the page read. In the console,
`window.__scenarioLedger.drop(["extracto.csv"])` drops files on the window and
`window.__scenarioLedger.changeReviews()` changes every pending review.

Select one in the control or in the address:

```text
/scenarios.html?scenario=throttled&lang=es
```

| Parameter  | Values                                                        | Meaning                                                                                                                                                                                                                            |
| ---------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scenario` | a name from the table                                         | The scenario to start in                                                                                                                                                                                                           |
| `lang`     | `en`, `es`, `ca`, `hu`                                        | The output language the host reports                                                                                                                                                                                               |
| `latency`  | milliseconds                                                  | The fixed delay before a sign-in or sign-out answer, 600 by default                                                                                                                                                                |
| `bar`      | `off`                                                         | Hide the scenario control, for a clean screenshot                                                                                                                                                                                  |
| `records`  | a count                                                       | Fill the log with that many generated records, up to its ring size                                                                                                                                                                 |
| `feed`     | milliseconds                                                  | Keep the log growing: twenty more records at that interval                                                                                                                                                                         |
| `calendar` | `behind`, `ahead`, `straddling`, `busy`                       | Another shape of the fixture calendar: all of it behind its day, all ahead, that day inside a month, or the turn of a year with nine windows open at once (evaluated on 2027-01-12)                                                |
| `ledger`   | `empty`, `refused`, `unknown`, `unavailable`, `slow`, `large` | How the made-up ledger answers: nothing recorded, every write refused, every write landing with an outcome that is not observed, nothing readable, every answer four seconds late, or five thousand more movements in October 2026 |

The terminals show deterministic fixture sessions in the real xterm view: type
`exit` in the console or `exit()` in the Python tab, or press `q` in the TUI, to
see an exited session, then Enter to restart it.

The embedded TUI stays behind the shared loading view while it resumes sign-in
and builds its first screen. Process startup alone does not reveal the terminal.
The TUI reports presentation readiness through OSC 777; the pane waits for
buffered output to settle and render before showing it. A login prompt needing
input, a retry screen, or an exited process remains visible. Terminal output and
cursor replies continue flowing while covered, and hiding the pane keeps its
session.

The documentation pane shows a stand-in documentation site. The development
server starts it beside itself, on the same address and fixed port 15372; the
preview server of the browser scenarios starts it on 15374 and hands the port
to the built page it serves.
The same host name with another port is a different origin, as
the documentation is in the desktop window, and it is reachable from wherever
the page is opened, another device included. Its pages load the real desktop
bridge script from `docs/_static/`, so navigation, search, appearance, zoom,
shortcuts and context menus cross a real `postMessage` boundary.

To open the page from another device, use the server's default `0.0.0.0` binding
and name the host in
`CADRUMO_DESKTOP_ALLOWED_HOSTS`, a comma-separated list read from the
environment or from `.env.local`.

### What a scenario proves

A scenario is design and test evidence only. The scenario host answers from
data: a sign-in it accepts authenticated nothing, and its clipboard is a
variable. Nothing seen here verifies the Tauri host, the runtime, the packaged
documentation or the `cadrumo-docs` scheme.

The scenario host cannot reach the product. Only `scenarios.html` loads it, and
the production build declares `index.html` as its one input. The build itself
refuses any module under `src/dev/` or `dev/` and any story
(`dev/product-boundary.ts`), the linter refuses the import, and
`tests/bundle.spec.ts` checks the built output.

## The component catalogue

```sh
npm run storybook
```

The catalogue is Storybook on the shell's own theme, at fixed port 6006 of the
configured address. An occupied port is an error. Its toolbar switches
the colour scheme and the chrome language, and every story is drawn on a real
shell surface inside the application's own providers.

| Group       | Holds                                                                                                           |
| ----------- | --------------------------------------------------------------------------------------------------------------- |
| Foundations | Colour roles, type, spacing, radii, density, elevation and every icon                                           |
| Primitives  | Buttons, fields, feedback, overlays and navigation: the components under `src/components/ui/`                   |
| Shell       | Sign-in, the command palette, settings, the rail, pane headers, the split and the log view, each in every state |

A story sits beside its component as `<Name>.stories.tsx` and takes fixed
data: a story proves presentation, never a host. `npm run storybook:build`
writes a static catalogue under the build directory; it is never packaged.

With the catalogue running, `npm run shots` photographs every story in both
schemes into the build directory's `test-results/catalogue`, and fails on a
story that did not render, a typeface that did not load or a refused request.

| Option      | Default      | Meaning                                    |
| ----------- | ------------ | ------------------------------------------ |
| `--filter`  | every story  | A regular expression over story ids        |
| `--schemes` | `light,dark` | The colour schemes to photograph           |
| `--locales` | `en`         | The chrome languages, from `en,es,ca,hu`   |
| `--width`   | `1280`       | Viewport width; `--height` defaults to 800 |
| `--scale`   | `1`          | Device pixel ratio                         |

## The design system

One theme drives every element. A component names a role or a token and never
a value, so a change of palette, density or type reaches everything at once.

| Layer       | Where                       | Rule                                                                                        |
| ----------- | --------------------------- | ------------------------------------------------------------------------------------------- |
| Colour      | the generated palette       | Generated from the documentation theme, which is the colour authority; never edited by hand |
| Roles       | `src/styles/theme.css`      | Maps palette values to roles (`background`, `chrome`, `card`, `selected`, `ring`, …)        |
| Tokens      | `src/styles/tokens.css`     | Lengths in rem: type scale, radii, density, icon sizes, fixed widths, layers and motion     |
| Primitives  | `src/components/ui/`        | shadcn/ui components on Radix, restyled to roles and tokens; they know nothing of Cadrumo   |
| Components  | `src/components/`           | The shell's own parts, built only from primitives                                           |
| Composition | `src/App.tsx`, `src/shell/` | State, the action registry and the host port; the only layer that talks to a `Host`         |

The linter holds what can be held mechanically: a primitive imports no
component and nothing of the shell or the host contract, only the Tauri adapter
imports `@tauri-apps/*`, and nothing in the product imports `src/dev/` or a
story. A component may read the shell's strings, metrics and types from
`src/shell/`; it never imports `src/App.tsx`.

Styles have one shared entry, `src/styles/shell.css`, imported by the product
and development CSS entries. `tokens.css` owns dimensions, query thresholds,
layers and motion; `theme.css` owns semantic colors and elevations; `fonts.css`
owns bundled typefaces; `base.css` owns document, focus and reduced-motion rules;
`utilities.css` owns token-backed content grids and third-party adjustments.
There are no CSS modules: components compose utilities and shared primitives.

Pills use the solid, borderless variants in `ui/badge.tsx`. Status labels,
counts, sent-file chips and toasts use `Badge`; interactive filter pills use
the `Button` pill variant. Calendar windows read the same badge variants,
with rounded ends only where the window begins or ends. Colour, type and
spacing come from the shared palette roles and tokens. Keyboard focus and
selection keep their shared indicators.

Lines are few. Where the chrome meets content, the change of surface is the
edge: a pane header, the rail, the title bar and a toolbar draw no hairline.
A raised or floating surface is edged once, by its elevation shadow, never by
a border as well. A box that only groups or quotes, such as a plan entry, a
package listing or a keycap, is a wash of ink (`bg-accent`) with no drawn
rectangle. A border is kept for the edge of a control (a field, an outline
button, a switch), for a state that must be told apart (a refused file, the
chosen option, today), for rows in a scrolling list, and for the rules a
document's own tables and quotes carry. A splitter rests in the divider
colour and takes the focus colour only under the hand.

The brand is one lockup, `Logo`: the documentation's coloured mark beside the
configured product name set in the text face, in capitals, semibold and
tracked. The mark's sizes are the `mark` tokens; the loading page draws the
same lockup stacked. The documentation's display serif is not used for the
name in the window: it is a display cut whose hairlines go faint at the sizes
a title bar has.

Public shell components use PascalCase filenames under `src/components/`.
Feature internals live in `calendar/`, `account/` and `records/`, with a descriptive
component per module. Generic primitives keep shadcn's kebab-case filenames
under `ui/`. Stories stay beside their component. Non-component helpers use
camelCase `.ts` files, and host subscriptions live in `src/shell/use*.ts`.
Import the defining module directly; do not add barrel exports or forwarding
components.

Tables of records compose `ui/data-grid.tsx`. `DataGrid` is the windowed,
editable grid: one tab stop with a roving active cell, rows by stable key,
sticky header and edge columns, resizable and reorderable columns, row and
cell-range selection, and editors that commit with Enter, Tab or Shift+Tab.
It holds no words: the caller passes its accessible name, the position
phrase it announces, row and cell descriptions, and the editors (a
`DataGridTextEditor` or a `Combobox`). `DataTable` is the plain sortable
table for short lists that are read and opened. Neither takes a shell chord,
and controls inside a cell take `tabIndex={-1}`. A modal editor beside a
table is a `Sheet`; a filter in force is a `FilterChip`.

Pane placeholders compose `EmptyState` from `ui/empty.tsx`; product components
do not reconstruct its icon, heading and description layout. Workspace headers
compose `PaneHeaderFrame` from `ui/pane-header.tsx`, including its shared
maximize gesture and exclusion of interactive controls. Keep implementation names
and transport codes out of ordinary prompts; diagnostic views own technical detail.

`src/shared/` holds dependency-free helpers reused across features, such as
ISO calendar-date arithmetic and cached locale formats. These modules import
no components, shell policy, IPC or host adapter. Product-specific shared rules
stay under their shell owner: `calendarEntries.ts` owns entry identity, windows
and urgency; `records.ts` owns severity ranking and record serialization. Keep
focus restoration, scroll positioning and read-refresh policy with the surface
that owns their behavior.

`npm run check` enforces component filenames, import boundaries and token use,
and tests these guards with deliberate violations. Literal dimensions, colors,
layer numbers and durations are rejected in components and stories. Structural
grids, system colors in forced-color mode and geometry computed from data
remain valid arguments. Define a new design measure once in `tokens.css` and
reference it through a variable or a named utility.

Conventions a new component follows:

- **Colour** comes from a role utility such as `bg-card` or
  `text-muted-foreground`. Hover and the chosen surface (`accent`, `selected`)
  are washes of ink over whatever they sit on. Faint text has no contrast to
  spare for a tinted surface: on a chosen row use the secondary text colour.
- **Size** comes from the density tokens: `h-control-xs` for a button in a
  header, `sm` in a toolbar, `md` in a dialog, `lg` for the rail and tab rows.
  Under a coarse pointer every step is at least a fingertip, with no change in
  the component.
- **State** is said by the element and styled from what it says:
  `aria-pressed` for a toggle, `aria-expanded` for a button that opens a
  surface, `aria-current` for the current row. A chosen item carries a bar as
  well as a surface, so no state rests on a tint alone.
- **Icons** come from the one registry in `src/components/ui/icon.tsx`, by
  name. An icon-only control is an `IconButton`, which always has a name and a
  tooltip. The one exception is a control repeated in every row of a list,
  such as a log record's detail toggle: a named `Button`, since a tooltip for
  each row would cost more than it tells.
- **Focus** is the single outline declared in `src/styles/base.css`; a component
  may move it inward, never restyle it.
- **Text** is a chrome string. Add it in English, Spanish, Catalan and
  Hungarian through `python -m dev.locales set-batch`, declare its key in
  `dev/locales/desktop_chrome.py`, and build `desktop-frontend-generated` again.
- **A component's module** exports components and types, nothing else. A
  value beside a component turns every edit of that file into a page reload
  in the development server. Words and helpers that others share live in a
  module of their own, as `src/components/accountWords.ts` and
  `src/shell/records.ts` do. The primitives keep the registry's habit of
  exporting their variants.

To add a primitive from the shadcn registry, run its CLI from this directory
(`components.json` points it at `src/components/ui/`), then restyle what it
wrote to roles and tokens and remove any dependency it added beyond the ones
already declared. The class merger is the local `@/components/ui/cn`.

### Editing your profile

Open **Your profile** from the rail or account menu. Search saved details, select
a section, or filter to missing required information. Individual fields and
repeatable entries use the same registered operations and validation as the CLI
and TUI. Sections collapse individually; full screen adds a section sidebar.
Name, contact and address fields provide browser autofill hints. AEAT
authentication opens the protected setup editor.

**Sync from AEAT** checks the saved taxpayer identity and authentication method
before a Censo pull. Missing details link to the tax-ID field or protected AEAT
setup, then return to synchronization. The current importer covers the fiscal
address, postcode and cadastral reference; it does not complete all profile
sections. Review shows saved and incoming values and preserves manual answers.
Saving or discarding is bound to the exact runtime review. Runtime notifications
update progress; a 30-second recovery check covers missed notifications.

Browser scenarios `censo-ready`, `censo-nie` and `censo-uncertain` exercise review,
missing NIE support-number setup and an interrupted request. They do not contact
AEAT. `user-profile` uses the canonical schema projection with synthetic values;
regenerate it with `uv run --no-sync python -m dev.desktop_profile_fixture`.

The desktop's `Host.userProfile` port reads a complete revision-pinned overview
through the held runtime connection. Changes made by another frontend trigger
a value-free runtime signal and a coalesced refresh. Open drafts retain their
original revision: conflicting edits cannot overwrite newer data. An uncertain
save keeps its draft and requires a refresh before retrying. Signing out removes
the page and rejects late read responses.

### Profile views

The window can show read-only views of the signed-in profile: the filing
calendar, and the notification counts behind the rail's Messages button. They
are an optional part of the host port, `Host.views` in `src/shell/host.ts`,
typed in `src/shell/views.ts`.

- **A host without views is a complete host.** The shell then draws no
  button, action, chord or page for one, so nothing leads to a view that
  cannot load.
- **The desktop host reads them over the signed-in person's relay**, as it
  reads the profile: `profile_views_calendar` runs `overview.calendar` and
  `profile_views_notifications` runs `live.notifications.latest`, then
  `live.notifications.show` for that capture. The window names no operation,
  and the host keeps nothing it reads.
- **A view is read for a profile, when something shows it.** The calendar is
  read when its page is shown, and not again for being put away and brought
  back within half a minute; its Refresh always asks. A calendar on screen
  when the local day changes is read again, since every distance on it is
  counted from the day it was read, and its mark is called today only where
  the day the product evaluated is today here. The counts are read
  when the profile becomes readable and when the window is returned to, at
  most once a minute. What was read is
  dropped when the profile or its sign-in changes. A read that is refused has
  the account's status read again, since the account may have changed
  underneath.
- **Not known is never drawn as empty.** A calendar that is loading, withheld
  or failed says so and is never an empty calendar. Messages shows a count,
  or nothing when none is unread, or a hollow pin with the reason in its name
  and tooltip.
- **Withheld, a view says what the TUI pane says**, by the same component,
  `SignedOut`, with the same ways on.
- **The types are what a host must return.** The calendar mirrors the
  product's calendar read, entries and observed events, field for field,
  including `opens_on`, the day an obligation's filing window opens; a host
  that cannot supply it returns null. A warning is the product's own
  sentence in the read's language, and a profile without a declared taxpayer
  model is said as a warning rather than drawn as nothing due. The
  notification summary is counts only: the rows it is counted from carry
  names and tax numbers, and they do not reach the window. A row whose read
  mark was not captured is not counted as unread.

The calendar has two faces over the one read, in
`src/components/FilingCalendar.tsx`:

- **The months** (`src/components/calendar/CalendarMonths.tsx`, laid out by
  `src/shell/calendarGrid.ts`) draw each obligation as a bar across the days
  its window is open, ending on the day that binds, in a row of its own where
  windows overlap. A window is named in full, Modelo and period, where it
  is first drawn in a month; the weeks it goes on across carry its Modelo
  alone. Its ends are rounded, and hovered it takes the shared wash over its
  own fill (`hover-wash`). What was observed is a mark on its day, filled for a
  filing made and hollow for a message from the agency. The day the product
  evaluated is marked: filled and said as today where it is today here,
  ringed and said as its date where it is not. The months run from the
  range's first to its last, and on to the month in which the last window
  open in the range closes, a year past the range at most.
  A window uses the shared solid pill fill and carries its state's icon,
  including in narrow windows. Where the system forces its colours the fill,
  the mark, the day and an outline on what is chosen remain.
  A window whose opening is null is drawn on its closing day alone and says
  the opening was not reported: an opening is never guessed. A week shows
  at most four rows. With more windows than that it keeps three rows of
  them and gives the fourth to a count of the rest: what is late first, then
  what is due, what is not known and what is filed, and of each the one that
  closes soonest, whenever it opened. Such a month has a control beside its
  name that draws it whole and back. What is chosen is always drawn, in
  place of what its week would keep last, so the month is no taller for a
  choice and nothing moves under the hand that made it. The week begins
  on the day the chrome language begins it.
- **The list** says where each obligation stands, by month, with what was
  observed in each month under its obligations.

A page at least `--calendar-split` wide, a maximized pane on most windows,
shows both: the months, and the list as a second column that scrolls by
itself. A narrower page shows one, the months first, with a switch that
stays in reach as the page scrolls; a page at least `--calendar-tall` high
keeps its whole head there, counts and all. Each face opens on where the
person is: the current month, the list's mark for today, or the obligation
chosen. After that the place is theirs, in each face: the month that begins
the row at the top of the view, or the row at the top of the list, is put
back where it was under the head whenever the face is laid out anew, by a
pane resized or maximized or by coming back from the other face. A scroll
the layout caused, or the page itself made, is not taken for the reader's.
The shell keeps the face, the choice, the months drawn whole and both
places while the page is put away, and lets them go with the profile.
Choosing an obligation in one face marks it in the other and brings it into
view. An obligation is one keyboard stop and one thing read aloud however
many weeks its bar crosses; from one, the arrow keys go to the next and the
one before, and Home and End to the first and the last. The counts in the
page's head are the key to the bars: each carries the colour and the mark
its reading has among the months, and beside them stands the key to the
marks on the days. Every state is also said in words. A control named in
the language's word for today brings both faces back to where the calendar
stands; it is named by the day instead where the calendar was worked out
for another one.

A new view takes its type and method in `src/shell/views.ts`, a fixture and
an answer in the scenario host, a hook in `src/shell/` that owns when it is
read and dropped, and then its surface.

### The Ledger page

The rail's Ledger button, or its palette entry, shows the profile's ledger
in the first pane, where the host offers the ledger port. The pane's header
holds the page's sections (Movements, Invoices, Documents, and Rules,
Registers and Health under Setup), its period and its actions.

- **The period** is one dropdown with the previous and next period beside
  it. Inside, the year moves by its own buttons, with no bound inside the
  period grammar. Each year that has movements, read from the ledger, is a
  button that moves the dropdown to that year. `PeriodSelector` also has a
  year-only mode.
- **A period is read whole** before anything is drawn from it. Reading, a
  failed read (with its code, and a Retry the page never runs by itself),
  an empty period and a withheld page are each said as such.
- **Only presentation is kept**: the section, columns, density, grouping,
  saved view and inspector, in the layout store. The period, every value
  and anything staged stay in the page's memory and go with the profile.
- **No shell chord** is the page's, and the documentation's Alt+Left and
  Alt+Right are not taken while it is shown. No bare letter is a shortcut:
  in the movements grid a typed character is typing. The page's actions
  are in the palette.

The Movements section, in `src/components/ledger/movements/`, draws the
stored movements of the period on `DataGrid`; nothing staged changes what a
cell, a count or a sum shows.

- **The readiness strip** counts, as a glyph and a number, the movements
  readiness found something on, those to classify and those with no euro
  rate, each hidden at zero; with nothing left it is one tick, and a hollow
  mark while nothing current was checked. Each pill, and each reason chip
  ("Category 5"), filters the grid to exactly the movements it counts,
  replaces the selection with the first of them, and leads to its column.
- **The toolbar** has the search (every word on its own, months by name,
  figures written with a dot or a comma, and a count of what other periods
  hold), the filters with their chips, the saved views, grouping (with
  each group's count and sums per currency and direction, and its quick
  actions), sorting, the column chooser with its presets, and density.
- **A period is refined here**; "All periods" is read in part, so only the
  product's own sort axes and its group-label partition are offered there,
  and the toolbar says how much of it is loaded. The account, import and
  import-note filters are the product's own: the grid keeps the movements
  their list reads return.
- **Classifying** goes through one command, `classifySelection` in
  `src/shell/ledgerCommands.ts`: Alt+B, Alt+P and Alt+M, the palette, the
  group headers and the inspector all reach it. Business asks for a
  category and Mixed for a share; a selection with hidden movements is
  refused until the person shows them or keeps only the visible ones.

### Keyboard

Every pointer path has a keyboard path through the same action.

| Keys                                  | Does                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------- |
| Ctrl+K, or Ctrl+Shift+K in a terminal | Open the palette: documentation search and every action                |
| F6, Shift+F6                          | Move between the first pane's page, the TUI, the bottom panel and rail |
| Ctrl+Shift+T                          | Show or hide the TUI                                                   |
| Ctrl+Shift+D                          | Show or hide the filing calendar, where the host offers it             |
| Ctrl+`                                | Show or hide the bottom panel                                          |
| Ctrl+Shift+1, 2, 3                    | Console, Python shell, Logs                                            |
| Ctrl+Shift+M                          | Maximize the focused area, or restore the layout                       |
| Ctrl+,                                | Settings                                                               |
| Alt+Home, Alt+Left, Alt+Right         | Documentation home, back and forward                                   |
| Ctrl+=, Ctrl+-, Ctrl+0                | Documentation zoom                                                     |
| Ctrl+Shift+C, Ctrl+Shift+V            | Copy and paste in a terminal                                           |
| Alt+B, Alt+P, Alt+M                   | Ledger movements: classify the selection as Business, Personal, Mixed  |
| F8, Shift+F8                          | Ledger movements: the next or previous readiness issue                 |

On macOS the primary modifier is Command. The rail and the tab row are one tab
stop each, moved through with the arrow keys. A splitter takes the arrow keys,
Home, End and Enter. The log's records are one tab stop: arrows, Home and End
move, Enter opens a record's detail, and the menu key opens its menu. A modal
surface owns the keyboard: no chord reaches the shell from under one.

## Check and test

```sh
npm run check   # type check, lint and formatting
npm test        # the browser tests, against a fresh production build
```

The test run builds the production bundle and the scenario bundle itself, then
runs three Playwright projects, each on a server of its own that the run starts
and that must not already be running:

- `product` drives the production build through `vite preview`, with no host or
  with a faked Tauri transport (`tests/desktop.spec.ts`), under the window's
  own content security policy, and checks the built output
  (`tests/bundle.spec.ts`).
- `scenarios` drives `/scenarios.html` (`tests/scenarios/`) from
  `vite build --mode scenarios`, a minified build of the development entry with
  the scenario host and the documentation fixture, written under the build
  directory's `desktop/testing/scenarios` and served by
  `vite preview --mode scenarios`. Nothing in it watches the source tree, so a
  file saved while the tests run cannot reload a page in the middle of a test.
- `hot-reload` (`tests/hot-reload/`) is the one spec that needs Vite's own
  client: it checks that the development entry disposes its shell when Vite
  hot-updates it. It runs on a development server started in
  `--mode scenarios`, whose pages have their hot-update socket replaced by a
  mock.

| File in `tests/scenarios/` | Holds the shell to                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| `scenarios.spec.ts`        | What each scenario presents, and the sign-in rules: one submission, no retry               |
| `accessibility.spec.ts`    | An axe audit of every major surface in both schemes                                        |
| `keyboard.spec.ts`         | Tab stops, arrow-key patterns, chords, and where focus goes when a surface opens or closes |
| `touch.spec.ts`            | A phone-sized touch screen: finger-sized controls, no overflow, taps and touch drags       |

Run one project with `npm test -- --project=scenarios`. All three servers start
for any project, and the builds run each time. To run the scenarios alone,
building only their bundle, use
`npx playwright test -c playwright.scenarios.config.ts`.

### Speed and memory

```sh
npm run benchmark -- --check
```

The benchmark builds the product and a minified scenario page, then measures
bundle size, start-up, idle memory, the palette, a splitter drag, a log of ten
thousand records, and forty rounds of opening and closing the overlays to show
that nothing accumulates. It also measures the filing calendar over a
fixture with nine windows open at once: how long it takes to be drawn, forty
rounds of its faces, a month drawn whole and a choice, and a drag of the
split out to where both faces fit and back; and forty rounds of the sign-in
dialog, put aside and opened again, turned into the form that creates a
profile and back, with another profile chosen; and the Ledger page over a
period of five thousand movements: how long the period takes to be read in
pages and drawn, a scroll through it, every shown movement selected and a
sort of the whole window. It writes `test-results/benchmark/benchmark.json`
in the build directory. Each number has a loose budget in the script, and
`--check` fails the run when one is exceeded. The numbers describe the machine
they were taken on: compare runs, not hosts.

## Stable hooks

The packaged acceptance run (`native/desktop/tests/`) drives the real window by
these, so a redesign keeps them. They are contracts, not styling.

| Hook                                                     | Contract                                                                                                                         |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `.rail-group`                                            | The first starts with search, then docs home, and goes on with TUI, the shortcuts and the panel toggles; the last holds settings |
| `.palette`, its `combobox`                               | The palette and its one input                                                                                                    |
| `.palette-results > section`                             | The first section is the documentation's while a query searches it                                                               |
| `.palette-title`, `.palette-chord`                       | A row's title; a chord is on action rows only                                                                                    |
| `.settings`                                              | Its first `radiogroup` is appearance: follow, light, dark; Escape closes it                                                      |
| `#profile-password`, `.sign-in button[type=submit]`      | The sign-in form                                                                                                                 |
| `#tab-<kind>`, `[data-terminal="<kind>"]`                | A panel tab and its terminal, `hidden` while not shown                                                                           |
| `.xterm-screen`, `.xterm-rows`, `.xterm-helper-textarea` | xterm's own elements                                                                                                             |
| `.docs-frame`, `.pane-docs .pane-title`                  | The documentation frame and its pane's title                                                                                     |
| `.panel-separator`, `.logview-list`                      | The bottom panel's handle and the log's list                                                                                     |

The browser tests also select `.pane-tui`, `.pane-head`, `section.panel`,
`.main-area`, `.tabstrip`, `.split` with `split-row` or `split-column`,
`.split-separator`, `.logview`, `.filter-text`, `.record`, `.source-banner`,
`.terminal-note`, `.terminal-host`, `.rail`, `[data-pin]` on a rail button,
and in the calendar `.calendar-page`, `.calendar-head`,
`.calendar-standing`, `.calendar-view`, `.calendar-months`,
`.calendar-month` with `data-month`, `[data-day]`, `.calendar-bar` and
`li[data-entry]` with `data-entry` (Modelo and period), `data-selected`,
`.calendar-grid-today`, `.calendar-event` with `data-event`,
`.calendar-more`, `.calendar-whole`,
`.calendar-list`, `.calendar-aside`, `.calendar-observed`,
`.calendar-today` and `.calendar-distance`, and on the Ledger page
`.ledger-page`, `[data-rail=ledger]`, `.ledger-period`, `.ledger-readiness`
with `[data-readiness]`, `.ledger-movements`, `.ledger-empty`,
`.ledger-failed` and `.ledger-loading`, and in its Movements section
`.ledger-grid`, `.ledger-count`, `.ledger-toolbar`, `.ledger-search`,
`.ledger-views`, `.ledger-filters`, `.ledger-columns`, `.ledger-chips`,
`.ledger-reasons` with `[data-reason]`, `.ledger-group-actions`,
`.ledger-hidden-selection`, `.ledger-elsewhere`, `.ledger-classify` and
`.ledger-toast`.

## What only the desktop window can show

Nothing above runs the Tauri host. The browser work is settled; these remain
to be checked in a built desktop package, on an interactive desktop, with
`desktop-packaged-test`:

- **Sign-in against the runtime.** One submission reaches the runtime, a
  refusal is not retried, and the canonical refusal codes arrive as the shell
  expects them. The last packaged run failed here on the letter case of a code
  (see below); the browser tests cannot see the host's answer.
- **Content security policy and the `cadrumo-docs` scheme.** The browser test
  applies the policy from the configuration template to the production bundle;
  the window applies the generated one to the packaged documentation origin.
- **Terminals.** Real PTY sessions, their timing, IME and clipboard, and F6
  leaving a focused terminal, which here is exercised against fixture sessions.
- **The documentation bridge.** F6 and the other chords pressed inside the
  packaged documentation are forwarded by its bridge script; the fixture site
  loads the same script, the packaged pages are a different build of it.
- **WebView differences.** The benchmark and the tests run in Chromium.
  WebKit, on macOS and Linux, has no scroll anchoring, so the log puts a
  reader's place back itself whenever what is drawn changes; check there that
  it holds while records arrive. The fade at the edge of a sideways-scrolling
  bar needs scroll timelines and is simply absent without them. Check both
  with reduced motion and with the system at 200 percent.
- **Profile views.** No host provides the filing calendar or the notification
  counts yet, so everything about them here is scenario evidence. When one
  does: the product's real answers against the types in `src/shell/views.ts`,
  how long a read takes, since each is a process, what a read answers once the
  sign-in has ended, and the calendar over a real profile's year: how many
  windows overlap in a week, and whether the host can say when each opens.
- **Touch beside a pane's edge.** A finger that lands on nothing of its own
  within about 30 px of the line between two panes is given to that line by
  the browser's touch adjustment and resizes the panes instead of scrolling.
  Measured in Chromium's touch emulation only; check it on a touch screen.
- **A screen reader pass** of the sign-in dialog, the palette, the log and the
  calendar.

### The packaged run of 2026-10-05 20:09

The findings of the last packaged run before this work, one by one. No
packaged assertion was changed.

| Finding                           | Cause                                                                                              | Where it is settled                                    |
| --------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `canonical-sign-in`               | The host answered `credential_rejected`; the assertion expects the canonical `CREDENTIAL_REJECTED` | Host or harness; the shell compares the canonical code |
| `python-prompt`, `python-unicode` | The Python session's first prompt and typed input arrived later than the harness waited            | Native: session start-up timing                        |
| `console-runtime`                 | The console did not resolve the packaged runtime on its path                                       | Native: package environment                            |
| `token`                           | The probe flags a `CadrumoDocs` global in the documentation page                                   | Documentation bridge script                            |
| `logs-flyout`                     | The harness waits for `[data-terminal="logs"]`; the log is `#panel-logs`, which is not a terminal  | Harness defect, reported, not edited here              |
| `localized-docs-home`             | Docs home did not reach the localized entry; the cause was not established from the run            | Native: to rerun                                       |
| `settings-docs-appearance`        | The target crashed during the check                                                                | Native: to rerun                                       |

That run's result files were removed with its build directory, so this table
is from the notes taken when it was read; a fresh run replaces it.

## Account and runtime signals

The native host exposes public account observations through
`sign_in_subscribe({ token, updates: Channel<SignInSignal> })`, returning a numeric
subscription. Dispose it with `sign_in_unsubscribe({ token, subscription })`.
The shell adapter offers this as `Host.observeSignIn(listener)` and returns a
cleanup function. The same document token and origin checks as other shell
commands apply; there is one current listener per host document.

| Signal `kind`                | Payload                                                                               | Design response                                                                                                                                                                                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sign-in-state`              | `revision`, `status: { supported, state, active_profile, runtimeAvailable, refusal }` | Update account and runtime indicators. `present` releases the account gate; `absent` offers sign-in for the selected profile; `unknown` shows uncertainty. A changed `active_profile` invalidates displayed profile data. `runtimeAvailable: false` offers Background Services recovery. |
| `manager-state`              | `revision`, `status: { state, failure }`                                              | Supervisor availability: `unsupported`, `starting`, `ready`, `recovering`, `waiting`, `stopping`, `stopped`, or `failed`. Recovery immediately gates private views, passwords and TUI access. Returning to `ready` requires a fresh canonical sign-in read before releasing that gate.   |
| `manager-observation-failed` | `revision`, `error: HostFailure`                                                      | Gate account access and show the public failure code; do not display private diagnostic messages.                                                                                                                                                                                        |
| `sign-in-observation-failed` | `revision`, `error: HostFailure`                                                      | Show the safe failure code and a retry/recovery prompt; do not display a signed-in state from an older snapshot.                                                                                                                                                                         |

The token-gated `manager_status`, `manager_subscribe({ updates })`, and
`manager_unsubscribe({ subscription })` commands supply these supervisor signals.
Subscriptions publish initial state and changes from the existing native watchdog;
the frontend adds no supervisor poller. Each host subscription rejects old revisions
and late answers after replacement or readiness loss. Recovery and failure use the
existing toast and account loading presentation. Fatal startup failures before the
window opens exit unsuccessfully rather than showing a window without supervision.
The manager browser scenarios verify presentation only; packaged native lifecycle
tests establish real authenticated IPC and recovery.

A subscription receives its first snapshot immediately, then changed snapshots
from the canonical CLI status producer, sampled every two seconds while
subscribed. Identical snapshots and failures are coalesced. Revision numbers
increase within a subscription and reset for a replacement listener. Failed
delivery removes the listener; an old document's cleanup cannot remove its
replacement. Host shutdown stops and joins the observer and its CLI children.

`active_profile` is a public label. Signals contain no credential, receipt,
profile UUID or runtime session capability. They inform presentation; a client
still authenticates independently over verified IPC. The shell consumes them
without needing focus or an additional status request for each notification.
The existing `logs_subscribe` channel separately supplies diagnostic batches;
manager records have `source: "manager"` and scrubbed lifecycle facts in
`context.lifecycle_event`. Diagnostic messages are not authentication triggers.

## Layout

| Path                                            | Holds                                                                          |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `index.html`, `src/main.tsx`                    | The production entry                                                           |
| `scenarios.html`, `src/dev/`                    | The development entry, the scenario host and its fixtures                      |
| `dev/docs-fixture/`                             | The stand-in documentation site and the server plugin that serves it           |
| `dev/product-boundary.ts`                       | The build check that keeps development modules out of the product              |
| `src/App.tsx`, `src/shell/`                     | Composition, the action registry, layout state and the host port               |
| `src/shell/views.ts`                            | The read-only profile views a host may offer, types only                       |
| `src/shell/ledger.ts`                           | The ledger port a host may offer: its admitted definitions and typed requests  |
| `src/styles/tokens.css`, `src/styles/theme.css` | The design tokens and the colour roles                                         |
| `src/components/ui/`                            | The primitives                                                                 |
| `src/components/`                               | Public shell components, feature internals and colocated stories               |
| `.storybook/`, `src/dev/catalogue/`             | The catalogue's configuration and its foundations stories                      |
| `src/ipc/contract.ts`                           | The published host and bridge contract, types only                             |
| `virtual:desktop-strings`, `…-palette.css`      | The generated chrome strings and palette, resolved from the build directory    |
| `scripts/`                                      | The development server, the catalogue launcher, its screenshots, the benchmark |
| `tests/`                                        | The browser tests                                                              |

Presentation preferences share the validated `cadrumo-shell-layout` store. Fresh
windows show Profile and the agent where available; the workspace opens on
request. Page selection, pane visibility and maximization, panel tab and size,
calendar face, profile filters and section expansion, and the chosen minimum
log level survive reloads. Resetting log filters returns to the host's level.
Search text, drafts and private page data are not saved as view preferences.
The pane header owns each page's title and maximize control; page toolbars
supply only their own actions.
