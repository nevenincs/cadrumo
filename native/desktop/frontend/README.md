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
  the scenario host and shows a dashed **Simulated host** control in the bottom
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
| `runtime-unavailable` | Unknown presence with no runtime to ask                                  |
| `unsupported`         | A platform without sign-in: no sign-in view, no Account section          |
| `loading`             | An environment, status, log subscription and sessions that never answer  |
| `empty`               | Signed in with no log records, silent sessions and no search results     |
| `error`               | Refused environment and status reads, an unreadable log, failed sessions |
| `logs-missing`        | A log source that reports missing, which is not an empty log             |

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

The terminals show deterministic fixture sessions in the real xterm view: type
`exit` in the console or `exit()` in the Python tab, or press `q` in the TUI, to
see an exited session, then Enter to restart it.

The documentation pane shows a stand-in documentation site served by the same
development server under `/docs-fixture/`. The shell reaches it on the other
loopback name (`localhost` when the shell is on `127.0.0.1`, and the reverse),
so it is a different origin, as the documentation is in the desktop window. Its
pages load the real desktop bridge script from `docs/_static/`, so navigation,
search, appearance, zoom, shortcuts and context menus cross a real
`postMessage` boundary.

### What a scenario proves

A scenario is design and test evidence only. The scenario host answers from
data: a sign-in it accepts authenticated nothing, its menus are drawn by the
shell because the native popup is not simulated, and its clipboard is a
variable. Nothing seen here verifies the Tauri host, the runtime, the packaged
documentation or the `cadrumo-docs` scheme.

The scenario host cannot reach the product. Only `scenarios.html` loads it, the
production build takes `index.html` alone as its input, and `tests/bundle.spec.ts`
searches the built output for it.

## Check and test

```sh
npm run check   # type check, lint and formatting
npm test        # build, then the browser tests
```

`npm test` builds the production bundle and runs two Playwright projects:

- `product` drives the production build through `vite preview`, with no host or
  with a faked Tauri transport (`tests/desktop.spec.ts`), and checks the built
  output (`tests/bundle.spec.ts`).
- `scenarios` drives `/scenarios.html` on the development server
  (`tests/scenarios/`). It reuses a development server that is already running.

Run one project with `npx playwright test --project=scenarios`.

## Layout

| Path                         | Holds                                                                |
| ---------------------------- | -------------------------------------------------------------------- |
| `index.html`, `src/main.tsx` | The production entry                                                 |
| `scenarios.html`, `src/dev/` | The development entry, the scenario host and its fixtures            |
| `dev/docs-fixture/`          | The stand-in documentation site and the server plugin that serves it |
| `src/App.tsx`, `src/shell/`  | Composition, the action registry, layout state and the host port     |
| `src/components/`            | The shell's components                                               |
| `src/ipc/contract.ts`        | The published host and bridge contract, types only                   |
| `src/generated/`             | Generated chrome strings and palette; never edited by hand           |
| `scripts/bootstrap.mjs`      | The build directory bootstrap                                        |
| `tests/`                     | The browser tests                                                    |
