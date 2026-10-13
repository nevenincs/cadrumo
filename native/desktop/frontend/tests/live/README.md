# Live agent specs

The live project runs the shared agent specs, `tests/scenarios/agent.spec.ts`
and `tests/scenarios/agent-prompts.spec.ts`, against the packaged desktop's
own window and the real agent backend. Playwright attaches to the window's
WebView2 over a DevTools port on the loopback address. It launches no browser
and starts no server.

## Run it

From the repository root, on the signed-in Windows desktop:

```powershell
just build-native Release bundle
just build-native Release desktop-packaged-host
just desktop-agent-live
```

The second command builds the remote-debugging desktop host. That host is
never staged or shipped. It admits exactly one `--remote-debugging-port=<port>`
in `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, and the lane sets that variable only
for the desktop it starts. Chromium binds the DevTools port to the loopback
address, and the lane refuses a port that listens anywhere else.

The lane:

- creates a fresh, marked storage root under `build/acceptance`;
- creates a synthetic profile through the package's `aeat` command line;
- signs the profile in with the password on standard input;
- stores your provider key into that profile with
  `aeat config provider set --secrets-stdin`;
- starts the desktop in a kill-on-close Job;
- runs this project;
- signs out and closes the window;
- fails if any process it started is still running;
- scans for the provider key prefix in the command lines of those processes,
  in every file under the run's directory, and in the Playwright traces and
  screenshots.

Exit 0 means every spec passed and both checks were clean, 1 means a failure,
and 3 means a prerequisite is absent.

The lane reads your key only from its own environment, as
`CADRUMO_LLM_CLAUDE_API_KEY`, and exits 3 naming that variable when it is
unset. It writes the key once to the set command's standard input. The key is
never placed on a command line, in a file, a log or another process's
environment.

Options, passed as `just desktop-agent-live <options>`:

| Option          | Meaning                                                      |
| --------------- | ------------------------------------------------------------ |
| `--attach-only` | Run only the attachment check, `attach.live.ts`              |
| `--served`      | Load the shell from `just dev`, with hot reload              |
| `--keep`        | Keep the run directory after a pass                          |
| `-- <args>`     | Pass the remaining arguments to Playwright, such as `-g ...` |

`--served` uses a second test host. Its shell is the development server's
address, so a change to the shell needs no rebuild while the Rust host, the
launcher and the agent stay real. Build it once with
`node native/desktop/tests/packaged/host.mjs --served`, with
`CADRUMO_CMAKE_BINARY_DIR`, `CADRUMO_BUILD_CONFIG` and `CADRUMO_NATIVE_CONTRACT`
set as the `desktop-packaged-host` target sets them. Run `just dev` in this
checkout first. The lane refuses a development server that another checkout
started.

## How the specs reach the window

`tsconfig.json` here resolves `@playwright/test` to `fixture.ts` for this
project only. The specs and `tests/support/agent.ts` import Playwright
unchanged. Their `page` is the desktop's shell, attached over the DevTools
protocol. Each test starts from the shell entry with empty web storage. An
address the specs open on the scenario page, `/scenarios.html?...`, leads to
the shell entry. Scenario queries select fixture behaviour that the desktop does
not have.

Checks that only the scenario host can satisfy can be skipped through the
project metadata:

```ts
const live = test.info().project.metadata.agentHost === "live";
```

The value is `"live"` in this project and absent in the `scenarios` project.
Examples of such checks are `window.__scenarioHostCalls` and the scenario
host's reply wording.
