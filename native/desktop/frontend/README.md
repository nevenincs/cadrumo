# Cadrumo desktop shell frontend

The React shell of the Cadrumo desktop window. It is developed in a browser:
the same components that run inside the Tauri window run on a Vite development
server, against a simulated host, with hot reload. Compiling the desktop host,
assembling a package or building the documentation is not needed to edit it.

## Prerequisites

- Node.js and npm, with dependencies installed by `npm ci` in this directory.
- CMake 4.4 or newer.
- The repository's development Python environment, which the generators run in.

## Bootstrap a build directory

The development server reads a few generated files from a CMake build
directory: the build paths, the product identity and the server address. The
shell reads two more from `src/generated/`: the chrome strings, projected from
the locale catalogues, and the palette, projected from the documentation theme.
One command writes all of them:

```sh
npm run bootstrap
```

It configures the standalone desktop project into `build/desktop-frontend` at
the repository root and runs the two generators. It compiles nothing and takes a
few seconds. Options:

| Option                  | Default                  | Meaning                                                |
| ----------------------- | ------------------------ | ------------------------------------------------------ |
| `--build-dir <path>`    | `build/desktop-frontend` | The build directory to prepare                         |
| `--host <address>`      | `127.0.0.1`              | The address the servers bind                           |
| `--dev-port <port>`     | `15370`                  | The development server port                            |
| `--preview-port <port>` | `15371`                  | The port that serves the production build to the tests |

Pass options after `--`, for example `npm run bootstrap -- --dev-port 15380`.
Run it again after a locale catalogue or the documentation theme changes.

Every other command here needs the build directory named in the environment:

```sh
# PowerShell
$env:CADRUMO_CMAKE_BINARY_DIR = '<absolute path to the build directory>'
# POSIX shell
export CADRUMO_CMAKE_BINARY_DIR='<absolute path to the build directory>'
```

## Develop in a browser

```sh
npm run dev
```

The server offers two pages.

- `/` is the production entry. Without a desktop host it uses the browser host,
  which fabricates nothing: every backend capability reports itself
  unavailable.
- `/scenarios.html` is the development entry. It mounts the same application on
  the scenario host and shows a **Simulated host** control in the bottom
  corner for switching scenario and language.

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
| `views-refused`       | Signed in, with every profile view refused: not an empty calendar        |
| `no-views`            | Signed in on a host with no profile views, as the desktop host is today  |

Every scenario but `no-views` offers the profile views (the filing calendar
and the notification counts behind the Messages button) from a fixture;
`empty` offers a calendar with nothing due and notifications never captured.
The desktop host offers none yet, so the product shows no way into one: the
views are design evidence until a host provides them.

Select one in the control or in the address:

```text
/scenarios.html?scenario=throttled&lang=es
```

| Parameter  | Values                 | Meaning                                                             |
| ---------- | ---------------------- | ------------------------------------------------------------------- |
| `scenario` | a name from the table  | The scenario to start in                                            |
| `lang`     | `en`, `es`, `ca`, `hu` | The output language the host reports                                |
| `latency`  | milliseconds           | The fixed delay before a sign-in or sign-out answer, 600 by default |
| `bar`      | `off`                  | Hide the scenario control, for a clean screenshot                   |
| `records`  | a count                | Fill the log with that many generated records, up to its ring size  |
| `feed`     | milliseconds           | Keep the log growing: twenty more records at that interval          |

The terminals show deterministic fixture sessions in the real xterm view: type
`exit` in the console or `exit()` in the Python tab, or press `q` in the TUI, to
see an exited session, then Enter to restart it.

The documentation pane shows a stand-in documentation site. The development
server starts it beside itself, on the same address and a port the operating
system assigns. The same host name with another port is a different origin, as
the documentation is in the desktop window, and it is reachable from wherever
the page is opened, another device included. Its pages load the real desktop
bridge script from `docs/_static/`, so navigation, search, appearance, zoom,
shortcuts and context menus cross a real `postMessage` boundary.

To open the page from another device, bootstrap with an address that device can
reach, for example `npm run bootstrap -- --host 0.0.0.0`, and name the host in
`CADRUMO_DESKTOP_ALLOWED_HOSTS`, a comma-separated list read from the
environment or from `.env.local`.

### What a scenario proves

A scenario is design and test evidence only. The scenario host answers from
data: a sign-in it accepts authenticated nothing, its menus are drawn by the
shell because the native popup is not simulated, and its clipboard is a
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

The catalogue is Storybook on the shell's own theme, at port 6006 of the
bootstrapped address (`-- --port <port>` chooses another). Its toolbar switches
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
| Colour      | `src/generated/palette.css` | Generated from the documentation theme, which is the colour authority; never edited by hand |
| Roles       | `src/theme.css`             | Maps palette values to roles (`background`, `chrome`, `card`, `selected`, `ring`, …)        |
| Tokens      | `src/tokens.css`            | Lengths in rem: type scale, radii, density, icon sizes, fixed widths, layers and motion     |
| Primitives  | `src/components/ui/`        | shadcn/ui components on Radix, restyled to roles and tokens; they know nothing of Cadrumo   |
| Components  | `src/components/`           | The shell's own parts, built only from primitives                                           |
| Composition | `src/App.tsx`, `src/shell/` | State, the action registry and the host port; the only layer that talks to a `Host`         |

The linter holds what can be held mechanically: a primitive imports no
component and nothing of the shell or the host contract, only the Tauri adapter
imports `@tauri-apps/*`, and nothing in the product imports `src/dev/` or a
story. A component may read the shell's strings, metrics and types from
`src/shell/`; it never imports `src/App.tsx`.

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
- **Focus** is the single outline declared in `src/theme.css`; a component
  may move it inward, never restyle it.
- **Text** is a chrome string. Add it in English, Spanish, Catalan and
  Hungarian through `python -m dev.locales set-batch`, declare its key in
  `dev/locales/desktop_chrome.py`, and run the bootstrap again.
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

### Profile views

The window can show read-only views of the signed-in profile: the filing
calendar, and the notification counts behind the rail's Messages button. They
are an optional part of the host port, `Host.views` in `src/shell/host.ts`,
typed in `src/shell/views.ts`.

- **A host without views is a complete host.** The shell then draws no
  button, action, chord or page for one, so nothing leads to a view that
  cannot load. The desktop host offers none yet: in the product none of this
  is on screen, and what the scenarios show of it is design evidence.
- **A view is read for a profile, when something shows it.** The calendar is
  read when its page is shown; the counts when the profile becomes readable
  and when the window is returned to, at most once a minute. What was read is
  dropped when the profile or its sign-in changes. A read that is refused has
  the account's status read again, since the account may have changed
  underneath.
- **Not known is never drawn as empty.** A calendar that is loading, withheld
  or failed says so and is never an empty calendar. Messages shows a count,
  or nothing when none is unread, or a hollow pin with the reason in its name
  and tooltip.
- **Withheld, a view says what the TUI pane says**, by the same component,
  `SignedOut`, with the same ways on.
- **The types are what a host must return.** The calendar mirrors the result
  of `app overview calendar` field for field. The notification summary is
  counts only: the rows it is counted from carry names and tax numbers, and
  they do not reach the window.

A new view takes its type and method in `src/shell/views.ts`, a fixture and
an answer in the scenario host, a hook in `src/shell/` that owns when it is
read and dropped, and then its surface.

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

The test run builds the production bundle itself, then runs two Playwright
projects:

- `product` drives the production build through `vite preview`, with no host or
  with a faked Tauri transport (`tests/desktop.spec.ts`), under the window's
  own content security policy, and checks the built output
  (`tests/bundle.spec.ts`).
- `scenarios` drives `/scenarios.html` on the development server
  (`tests/scenarios/`). It reuses a development server that is already running.

| File in `tests/scenarios/` | Holds the shell to                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| `scenarios.spec.ts`        | What each scenario presents, and the sign-in rules: one submission, no retry               |
| `accessibility.spec.ts`    | An axe audit of every major surface in both schemes                                        |
| `keyboard.spec.ts`         | Tab stops, arrow-key patterns, chords, and where focus goes when a surface opens or closes |
| `touch.spec.ts`            | A phone-sized touch screen: finger-sized controls, no overflow, taps and touch drags       |

Run one project with `npm test -- --project=scenarios`. Both servers start for
either project, and the build runs each time.

### Speed and memory

```sh
npm run benchmark -- --check
```

The benchmark builds the product and a minified scenario page, then measures
bundle size, start-up, idle memory, the palette, a splitter drag, a log of ten
thousand records, and forty rounds of opening and closing the overlays to show
that nothing accumulates. It writes `test-results/benchmark/benchmark.json`
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
and in the calendar `.calendar-page`, `.calendar-standing` and
`.calendar-distance`.

## What only the desktop window can show

Nothing above runs the Tauri host. The browser work is settled; these remain
to be checked in a built desktop package, on an interactive desktop, with
`desktop-packaged-test`:

- **Sign-in against the runtime.** One submission reaches the runtime, a
  refusal is not retried, and the canonical refusal codes arrive as the shell
  expects them. The last packaged run failed here on the letter case of a code
  (see below); the browser tests cannot see the host's answer.
- **Native menus.** The host draws context menus; the shell's own menu is the
  stand-in the browser shows. The menu key on a log record sends the row's
  position, which only the host can place.
- **Content security policy and the `cadrumo-docs` scheme.** The browser test
  applies the policy from the configuration template to the production bundle;
  the window applies the generated one to the packaged documentation origin.
- **Terminals.** Real PTY sessions, their timing, IME and clipboard, and F6
  leaving a focused terminal, which here is exercised against fixture sessions.
- **The documentation bridge.** F6 and the other chords pressed inside the
  packaged documentation are forwarded by its bridge script; the fixture site
  loads the same script, the packaged pages are a different build of it.
- **WebView differences.** The benchmark and the tests run in Chromium.
  WebKit, on macOS and Linux, has no scroll anchoring: a log that is not
  following may creep while records arrive. Check it there, with reduced
  motion and with the system at 200 percent.
- **A screen reader pass** of the sign-in dialog, the palette and the log.

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

## Layout

| Path                                | Holds                                                                 |
| ----------------------------------- | --------------------------------------------------------------------- |
| `index.html`, `src/main.tsx`        | The production entry                                                  |
| `scenarios.html`, `src/dev/`        | The development entry, the scenario host and its fixtures             |
| `dev/docs-fixture/`                 | The stand-in documentation site and the server plugin that serves it  |
| `dev/product-boundary.ts`           | The build check that keeps development modules out of the product     |
| `src/App.tsx`, `src/shell/`         | Composition, the action registry, layout state and the host port      |
| `src/shell/views.ts`                | The read-only profile views a host may offer, types only              |
| `src/tokens.css`, `src/theme.css`   | The design tokens and the colour roles                                |
| `src/components/ui/`                | The primitives                                                        |
| `src/components/`                   | The shell's components and their stories                              |
| `.storybook/`, `src/dev/catalogue/` | The catalogue's configuration and its foundations stories             |
| `src/ipc/contract.ts`               | The published host and bridge contract, types only                    |
| `src/generated/`                    | Generated chrome strings and palette; never edited by hand            |
| `scripts/`                          | The bootstrap, the catalogue launcher, its screenshots, the benchmark |
| `tests/`                            | The browser tests                                                     |
