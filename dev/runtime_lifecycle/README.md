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

Receipt reuse and MCP enrollment require working native credential storage. Windows
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
  request is refused. A separately pinned API-key MCP client requires actual human
  enrollment approval and native credential delivery. Its independent grant remains
  bound to A while the human selects B or signs out. The harness deletes delivered
  native credentials in teardown. After a runtime crash, genuine shared receipts
  can resume, while the old API-key session must explicitly authenticate again.


The Spanish tax agency (AEAT) status operation checks local provider readiness
through the application and worker machinery. It does not authenticate to AEAT remotely. Installed
manager entry dispatch, tray/window behavior, autostart, installer upgrades, and
live AEAT sessions require separate acceptance.

## Exercise an installed manager on a disposable Windows guest

The ordinary five-case driver campaign deselects the installed scenario. Selecting
installed acceptance requires the exact chosen guest UUID and dedicated account SID;
missing identity, host hardware, noncanonical storage overrides, persisted canonical storage or a
preexisting installation refuse before native registration. This lane changes the
guest registry and, for machine scope, its SCM service. Never run it on a development
workstation. Restore the guest baseline or use a fresh dedicated account between
scope campaigns; unregister does not erase taxpayer storage.

The shipping interpreter pins the native user storage destination and creates its
empty temporary directory before Python runs. The guard verifies that destination
and bootstrap, then checks freshness before importing COM support that creates a cache.

Use either the selected Hyper-V guest (`--installed-guest-kind hyperv`, the default)
or the selected QEMU template (`qemu`). The QEMU template uses native manufacturer
`QEMU`, model `CadrumoRuntimeGuest`, and the UUID explicitly configured by its owner.
Verify those CIM values on first boot. A command-line claim of disposability does
not replace native hardware, account, genuine logon and elevation verification.
User scope requires an unelevated token; machine scope requires elevation. Run in
the actual guest account's interactive logon, rather than a network-only token that
cannot use Credential Manager. Before mutation, the guard rechecks the actual
retained token and its LSA logon kind/owner/session, then reads an intentionally
nonexistent random credential target. Only native `ERROR_NOT_FOUND` (1168) proves
the facility; network-logon error 1312 or any other error refuses setup.

Copy the complete shipping application and services kit to the guest. Alongside
those immutable artifacts, transfer only these test-owner modules:

- `dev/__init__.py` and `dev/runtime_lifecycle/__init__.py`
- `dev/runtime_lifecycle/harness.py`, `client_probes.py`, and `installed.py`
- `dev/packaging/__init__.py` and `dev/packaging/command_execution.py`

The same scenario runs under shipping CPython, without installing pytest, a compiler,
SDK or development dependencies. Supply the verified native maintenance intent with
its two MSI paths bound to the copied guest artifacts, the actual native runner,
and both authored `wix/user-registration.wxs` and `wix/machine-registration.wxs`
beside that intent. Preserve all product codes, hashes, version and contract fields.
The native runner verifies the real products and owns the transaction.
Initial user-manager activation reuses the GUI's canonical
`native/desktop/src-tauri/src/python/manager_dispatch.py`, transferred as
`metadata/native/manager_dispatch.py` under the cohort root and bound by its
sealed inventory. The native same-logon manager and runtime IPC must still
verify after dispatch. Genuine login phases observe HKCU startup without
dispatching a replacement.

For example, with the transferred modules under `C:\acceptance\P1\owners` and a prepared
user-scope intent (replace UUID/SID with the selected guest/account):

```powershell
C:\package\app\python.exe -I -c "import sys; sys.path.insert(0, r'C:\acceptance\P1\owners'); from dev.runtime_lifecycle.installed import main; main()" `
  --plan C:\acceptance\P1\intents\maintenance-user.json `
  --runner C:\package\services\cadrumo-msi-maintenance.exe `
  --installed-vm-id SELECTED-UUID --installed-account-sid SELECTED-SID `
  --installed-guest-kind qemu
```

A successful direct invocation certifies only the immediate scenario: real native
install and registration, same-account manager/runtime readiness through native IPC,
unauthenticated refusal, password-authenticated CLI/TUI/MCP protected reads, exact
runtime death and recovery, stale-wire/session refusal, logout, and native unregister
with unavailable clients. Machine scope additionally verifies configured LocalSystem
auto-start SCM custody, stop/start, and same-package repair of a stopped service.
Both scopes also start the shipping Cadrumo executable in its existing command-only
health mode, then remove the installed manager. Machine scope stops the genuine SCM
broker; user scope terminates its exact retained, token-verified worker. The recovered
runtime must have a different verified boot, the live Cadrumo process as its native
parent, matching native logon identity, and membership in Cadrumo's owned Job.
Post-loss launch, readiness and boot-confirmation facts and real authenticated
CLI/TUI/MCP reads must succeed during the fixed 60-second observation window.
Slow or failed takeover fails acceptance. Cadrumo must then drain its owned runtime
and exit successfully without surviving Job members. The scenario restores the
installed manager before a requested held campaign commits its boot/login ownership.
No test-only lifetime command or substitute credential grants production authority.

The output explicitly retains `full_installation_acceptance: incomplete`. Machine
boot, user login, scope coexistence, and two-release upgrade/cutover/rollback require
separate observed campaigns. The canonical `check-msi-installation` dispatcher writes
its immediate receipt and fails while those obligations remain unproven, even when
the immediate subset passes. The direct invocation is useful subset evidence, not
full installed acceptance. Failures and teardown failures exit unsuccessfully.
The canonical dispatcher invalidates any previous receipt before starting. Its
1800-second outer timeout invokes the same preflight-admitted native unregister
owner and records failed acceptance with settled or unsettled cleanup. A refused
cleanup requires discarding/restoring the guest baseline. External termination of
the direct subset command requires owner recovery or baseline restoration too.

The same shipping-Python command supports `--phase hold|boot|login|cleanup` with
`--campaign-state C:\acceptance\machine-campaign.json`. Keep this dedicated test
artifact outside installation and taxpayer storage. `hold` runs the immediate
authentication, logout and recovery checks, then retains the authenticated manager
and installation. It atomically records the selected guest/account/scope and plan
and runner hashes. The synthetic profile coordinates and password use current-user
DPAPI; no plaintext profile secret is written to that artifact.

For machine scope, reboot the selected guest without automatic user login. Run
`boot` as a read-only observer under the same dedicated account. It verifies a
different native boot, configured auto-start LocalSystem service and its exact live
broker process, no user-associated WTS sessions, no interactive LSA logon for the
dedicated account, and no installed user manager/runtime processes. Query failures
fail the phase. The observer may use a network token; it performs no installation
mutation or authenticated application operation.

Then perform a genuine user login and run `login` through the actual interactive
account token (with elevation matching scope). Machine login requires successful
prelogin evidence from that same boot. User scope requires a new genuine login or
boot. This phase attaches to the automatically started manager without launching
one, verifies native IPC, and authenticates protected native/CLI/TUI/MCP reads.
Run `cleanup` interactively under the same scope after observations complete. It
uses the verified native unregister owner, waits retained manager/runtime handles,
requires unavailable CLI/TUI/MCP clients, and deletes only the synthetic profile's
receipt. Failed cleanup requires restoring the guest baseline.

Phases report `full_installation_acceptance: incomplete` until the actual final
cleanup closes every retained resource and all same-scope boot/login, scope and
upgrade obligations have passed. Only that cleanup can emit a complete receipt;
neither held state nor metadata proves an unexecuted campaign. Native admission intentionally
refuses simultaneous opposite-scope installation. After a successful hold, run
`--phase scope-conflict --conflicting-plan C:\acceptance\opposite-plan.json`
through the same account's genuine elevated interactive token. The second plan must
be the opposite scope from the same canonical cohort with a distinct, absent
installation prefix. The phase requires the actual native unsuccessful receipt
(`native_rolled_back`, `native_preparation_refused`), no second-scope MSI products
or registration/files, and unchanged retained original manager/runtime identities.
For an original machine installation it also authenticates protected native,
CLI/TUI/MCP reads. For an original user installation the elevated attempt reports
`attempted`; run `--phase scope-verify` with the same `--conflicting-plan` through
the original standard interactive token to authenticate those reads. This preserves
the original token binding rather than treating an elevated linked token as its
authenticated worker. The obligation passes only after these observations succeed.
Run the phases in order: `hold`, actual boot/login observations, scope
refusal/verification, ordinary-user GUI proof for machine scope, upgrade, then `cleanup`. Complete the original cohort's
boot/login and scope observations before replacing its registration.

For machine scope, run `gui-stop` with the genuine Highest interactive token,
`gui-user` with the genuine LeastPrivilege interactive token, then `gui-restore`
with Highest. All three keep the original machine plan and encrypted campaign
binding. The first phase stops the exact SCM broker and waits for its verified
worker/runtime settlement. The ordinary-user phase requests no service controls:
shipping Cadrumo must launch a confirmed new runtime on canonical user storage,
serve authenticated native/CLI/TUI/MCP reads and drain its owned processes. The
last phase restores genuine service custody and the original protected operation.
The native UAC `TokenLinkedToken` relationship binds each token's own raw logon ID:
Least must match the observed filtered counterpart, and restore must match the
original full token. SID, session, LSA ownership and boot remain verified. Machine upgrade and
full cleanup acceptance remain incomplete without this proof. Source/policy tests
do not substitute for its real guest execution.

For a user-scope held installation, run `--phase upgrade-rollback` with
`--successor-plan` and `--successor-runner` from a genuinely newer canonical
cohort. Keep `--plan` and `--runner` bound to the original cohort. The test installs
the successor through its native transaction while the original manager runs,
observes the real `upgrade_pending` wire notice, terminates only its verified
designated successor, and requires the original manager to restore a fresh runtime
with the actual failed-version marker and the same settled protected operation.
It then invokes real `--retry` and verifies successful successor cutover. If the
successor already committed before fault injection, the phase fails; restore the
baseline instead of claiming rollback. This proves rollback before manager cutover
commit, without claiming that the successor runtime never became ready.

Machine registration upgrades intentionally stop the broker and its workers.
Use `--phase machine-upgrade` with the same successor arguments for that scope;
it requires settled original worker exit and genuine successor service/worker
ownership rather than preserving the original worker. Both upgrade phases run
the protected continuation with the successor's bundled Python, require a new
runtime boot, reject the old session, and authenticate native/CLI/TUI/MCP reads.
The original DPAPI binding remains unchanged; session and operation coordinates
stay inside its encrypted payload. `upgrade-verify` is the bounded continuation
used by these phases, not an independent substitute for a real native upgrade.
After an attempted upgrade, provide the same successor arguments to `cleanup` so
it can select the actual registered native owner. Installation publication remains
at the successor after a user runtime rollback; the per-user failed-version marker
selects the previous runtime until retry succeeds.

The minimal guest runs this final `installed --phase cleanup` with shipped Python
and the transferred test-owner modules. It needs no CMake, uv or pytest installation.
The existing `windows_msi_build check-installation` dispatcher can finalize a held
campaign with `--installed-campaign-state`, `--installed-successor-plan` and
`--installed-successor-runner`. It must execute in the genuinely guarded selected
guest context with its builder dependencies; a host reading a saved guest receipt
does not pass that guard. The dispatcher executes cleanup itself and succeeds only
for its new, complete same-scope receipt. Its default immediate check still fails
full acceptance until the remaining campaigns run.
The CMake `check-msi-installation` target forwards these optional paths from
`CADRUMO_MSI_TEST_CAMPAIGN_STATE`, `CADRUMO_MSI_TEST_SUCCESSOR_PLAN` and
`CADRUMO_MSI_TEST_SUCCESSOR_RUNNER`; successor paths without a campaign state
fail configuration.

Upgrade/cutover/rollback requires two real compatible canonical release cohorts.
Restore the powered-off guest baseline
between independent installation scopes; unregister preserves taxpayer storage.

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
