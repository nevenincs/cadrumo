# Run runtime lifecycle acceptance on Windows

Run these tests from Windows commands, including non-desktop contexts. They exercise
real binaries and native interprocess communication (IPC) without opening or
driving Tauri. A successful run reports **5 passed** and records timing
measurements in JUnit.

See the [project overview](../../README.md), [development setup](../../CONTRIBUTING.md),
and [native build contract](../../native/CONTRACT.md#explicit-build-target-and-dependency-inputs).
Run every command in this guide from the repository root.

## Prepare the binaries

Use the normal project Python environment and a complete native package built
from the matching product version and authority generation. If the native build
is not already configured, the repository commands are:

```powershell
just setup-native-builder
just build-native Release bundle
```

This may build the complete package. These examples use the configured
`build/windows-x64` tree and its `stage/Release/app` package. Build and check the
debug-only manager driver. These targets require `BUILD_TESTING=ON` in the
configured build tree:

```powershell
cmake --build build/windows-x64 --config Debug --target rust_manager_lifecycle
cmake --build build/windows-x64 --config Debug --target check_manager_lifecycle
```

The shipping manager manages only the installed default storage root and refuses
storage overrides. The debug driver uses the same supervision core, native
package inspection, process lifetime, start claims, and restart
policy.

It runs against a fresh test root. The existing `fixture-test-mode`
feature gates it; release builds refuse that feature. It starts the real packaged runtime.

## Run the tests

Use PowerShell with access to the binaries and test storage. No desktop, session
number, or elevation admission gate applies. Native peer identity and real
profile credentials remain required.

```powershell
build/windows-x64/_deps/builder/Scripts/python.exe -B -m pytest -n0 -m integration dev/runtime_lifecycle/tests `
  --lifecycle-manager build/windows-x64/cargo/native/manager-lifecycle/x86_64-pc-windows-msvc/debug/cadrumo-manager-lifecycle.exe `
  --lifecycle-package build/windows-x64/stage/Release/app `
  --junitxml build/windows-x64/testing/lifecycle.xml -o junit_family=legacy
```

Both binary paths are explicit; there is no search for an installed manager or
reuse of a developer runtime. Pytest owns each temporary storage root. A native
kill-on-close Job contains the driver, runtimes, and their descendants.

Teardown requests a manager stop, reaps the test Job, closes connections, and removes the
synthetic profiles' keychain receipts. No login-start registration is created.

The same tests are registered as `bundle.runtime-lifecycle` in Windows CTest.
`verify`, `verify-app-distro`, and `verify-release` build the existing debug driver
and run that test against their assembled package. Compilation alone is not a
health result. For the fastest rerun against an already built package:

```powershell
ctest --test-dir build/windows-x64 -C Release -R '^bundle.runtime-lifecycle$' --output-on-failure
```

CMake writes this run's JUnit to `build/windows-x64/testing/Release/lifecycle.xml`.
Unavailable IPC or failed authentication fails verification; it does not skip the matrix.
For the quickest client-only check, add `-k packaged_client_authentication` to
the pytest command above. Canonical CTest still runs the complete lifecycle matrix.

Receipt reuse and API-key issuance require working native credential storage. Windows
Credential Manager can return error 1312 for a network logon even after real password
authentication succeeds. That fails the persistence matrix; it does not reject manager
startup or justify substituting test credentials.

The scenarios check:

- Password login, shared receipt reuse, A-to-B-to-A profile switching through the
  shipped command-line interface (CLI), immutable profile connection scope, logout,
  revoked old sessions, and rejection of a previously valid receipt proof.
- Two exact-runtime crashes. The kill uses a retained native handle checked
  against the verified IPC peer and test Job. Recovery requires the manager's
  exit/launch events, a different verified boot, and rejection of the old session.
  It also requires authenticated private responses and observation of a previously
  settled operation. The real `auth.local-read` status operation runs after recovery.
  A submitted `diagnostics.read` operation that has not started also survives
  and resumes through fresh authentication with its original operation identity.
  This uses its existing resume policy; `auth.local-read` does not permit resume.
  Abrupt owner loss retains the production ten-minute operation lease. The case
  checks that work remains unstarted until canonical takeover succeeds, then
  checks one execution phase before and after the second crash. This adds about
  ten minutes to the matrix; it uses no shortened lease or synthetic clock.
- Exact manager death leaves its authenticated runtime serving. An explicitly
  started successor adopts exact native custody, drains the survivor whose
  heartbeat channel was lost, then starts a replacement with verified readiness
  and a confirmed boot record. Old connections fail; private access resumes only
  after genuine authentication.
- Wrong-password refusal without authenticated private access.
- Packaged CLI profile reads, the packaged TUI overview adapter without mounting
  Textual, and packaged MCP stdio reads of a settled `auth.local-read` result.
  Each refuses protected access without authentication and after the manager/runtime
  stops. Ordinary MCP follows the current human profile and its real shared sign-in
  receipt; A-to-B switching changes its next protected request. A cross-profile
  request is refused. Acting as the person, the harness requests and approves an
  API key for A with native credential delivery; the agent never takes part. A
  second MCP server is launched with that key by `--credential-reference`. Its grant
  stays bound to A while the human selects B or signs out. After a runtime crash,
  genuine shared receipts can resume, and the key server authenticates again with
  its launch reference. The harness deletes delivered native credentials in teardown.


The Spanish tax agency (AEAT) status operation checks local provider readiness
through the application and worker machinery. It does not authenticate to AEAT remotely. Installed
manager entry dispatch, tray/window behavior, autostart, installer upgrades, and
live AEAT sessions require separate acceptance.

## Prove caller-owned storage and the held sign-in

Two drivers exercise a built package the way an external consumer does: only its
own programs (`bin/aeat`, `bin/cadrumo-runtime`, `bin/cadrumo-mcp`), on a fresh
root, with no manager, no login registration and no substituted OS or credential
store:

```powershell
just verify-caller-owned-runtime build/windows-x64/stage/Release/app
just verify-live-sign-in build/windows-x64/stage/Release/app
```

`verify-caller-owned-runtime` checks `cadrumo-runtime --configured-root`: its
readiness line, client discovery, password sign-in, stop when its stdin closes
(exit 64), and an unchanged installed default root. It reports `incomplete`
(exit 3) on a logon whose credential store refuses to keep a sign-in.

`verify-live-sign-in` checks `aeat config sign-in-hold` and attended MCP
admission, under `build/acceptance`:
- the command is registered, and MCP is refused before any sign-in;
- a declined ask and a connection naming another profile are refused;
- an approved ask is admitted, after checking that the asking process descends
  from the harness, and reads the profile's own data as `attended`;
- access ends after the holder signs out, the holder's stdin closes, a
  password-proven `config logout`, a profile-wide lock, the sign-in deadline, and
  runtime stop;
- no stored sign-in is left, the default root is unchanged, and no started process
  survives.

It also runs one reviewed operation. A ledger row is classified by the local
`qwen3:1.7b` text model on this machine. The pending review is read, inspected
and applied through MCP, and the classification is read back through the
command line. The harness serves the model itself: it runs `ollama serve` on
the loopback port, reading an existing model store (`--ollama-models`, default
`~/.ollama/models`) with pruning switched off, and stops it afterwards. It
refuses to share a server it did not start. Without the model the step is
unproven.

It waits out the sign-in deadline (about 15 minutes); `--skip-expiry` and
`--skip-review` leave those steps out and report `incomplete`. A step it cannot
prove is reported `incomplete`, never passed.

## Prove a reviewed operation is rejected without changing the row and applied once

```powershell
just verify-reviewed-operation build/windows-x64/stage/Release/app
```

Prerequisites: the package's own `bin/aeat`, `bin/cadrumo-runtime` and
`bin/cadrumo-mcp`, built with the optional `llm` extra (a core-only package
refuses local-model work with `ERROR_OPTIONAL_EXTRA_MISSING`); an installed
Ollama and an existing model store holding `qwen3:1.7b` (`--ollama-models`,
default `~/.ollama/models`); and a free loopback port 11434. No remote service is used and nothing is downloaded. The
attendance approval only admits the MCP connection; the review is answered on
its own interaction.

The driver runs each step as a real process on a fresh root under
`build/acceptance/reviewed-operation-*`, with the password only on a command's
standard input:

1. `aeat config profile create NAME --quiet --secrets-stdin`, then
   `aeat --profile-secrets-stdin config profile edit ...` with synthetic
   taxpayer facts and `config profile complete-setup`.
2. `cadrumo-runtime --configured-root`, then `aeat config sign-in-hold NAME`
   with the password on its first input line; its `held` event names the
   profile id.
3. `ollama serve` with `OLLAMA_MODELS` set to the store and pruning off.
4. `cadrumo-mcp` over stdio. Its first profile call raises an
   `attendance_request` on the holder, which approves that exact ask after
   checking that the asking process descends from the driver.
5. MCP `execute ledger.add` adds a synthetic row. The command line
   (`aeat app ledger list`, `aeat app ledger history ID`) records the row and
   its history.
6. MCP `execute ledger.classify.review`, then `observe` until the pending
   interaction is `review_available` with effect `none`, then `review` to read
   the proposal.
7. MCP `respond` with `reject` and the review's operation, interaction and
   revision. A rejection is a recorded decision: the command line lists the row
   exactly as before, and its history gains exactly one
   `ledger.transaction.llm_suggestion.rejected` audit event.
8. Steps 6 and 7 again with `apply`. The row is classified and reviewed by
   `llm:local-text:*`, the command line reads that classification, and the
   history gains exactly one `ledger.transaction.classified` event.
9. A second `apply` to the same interaction is refused, and the row and its
   history are unchanged.
10. Close the holder's input (`input_closed`, exit 0), stop the model server
    with its runners, and stop the runtime (exit 64). No started process may
    survive.

The root is removed afterwards; `--keep` keeps it, and a failed run keeps it and
prints its path. The driver exits 0 when every step held, 1 when one was
contradicted, and 3 when the model was unavailable or the package lacks the
`llm` extra.

## Inspect timing evidence

Open `build/windows-x64/testing/lifecycle.xml`. Each test's `lifecycle_seconds`
property contains a JavaScript Object Notation (JSON) object. Values are seconds;
fields appear only when the corresponding action ran.

| Field | Measurement |
| --- | --- |
| `startup_seconds` | Driver launch to exact-image verified runtime handshake |
| `password_login_seconds` | Password submission to authenticated login reply |
| `logout_seconds` | Logout request to runtime revocation reply |
| `failure_detection_0_seconds`, `failure_detection_1_seconds` | Kill request to observing the manager's exit event; includes polling delay |
| `reconnect_0_seconds`, `reconnect_1_seconds` | Kill request to a new verified runtime boot |
| `request_median_seconds`, `request_max_seconds` | Median and maximum of 12 authenticated session-status requests |
| `cleanup_seconds` | Manager stop and owned resource cleanup |
| `pending_operation_recovery_seconds` | Fresh authenticated continuation through expired-owner lease takeover and a protected settled result |

Startup, request, and recovery calls have bounded deadlines. The measurements
report observed latency; they are not a performance service-level promise.

## Diagnose failures

A missing driver or incomplete package is a setup failure.
A version or authority mismatch is a real handshake refusal:
use matching package and project inputs.

If a command fails, retain the pytest summary and
bounded refusal code. Include those, the build command, and package version in a
[reproducible issue](https://github.com/nevenincs/cadrumo/issues). Do not attach
credentials or profile storage contents. Authentication failures and incomplete runs
are not passing acceptance evidence; these scenarios do not skip them.
