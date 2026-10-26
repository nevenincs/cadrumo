---
tags:
  - '#research'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:82dba76c74ead1acf8607e812341064999c93a800a34656b0427ad1606c89d37'
related:
  - "[[2026-10-03-runtime-manager-architecture-research]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - '[[2026-10-03-runtime-without-service-manager-scope-removal-audit]]'
---

# `runtime-manager-architecture` research: `Runtime manager requirements and platform mechanisms`

Question (operator, 2026-10-04): the installed runtime must be running for the CLI, TUI and MCP servers to work, and nothing in the product starts it. The operator has stated that runtime management is a definite target. The earlier refusal was aimed at a bare Windows scheduled-task launcher, and the `2026-10-03-runtime-without-service-manager-adr` deferral is interim. This record lists two kinds of requirement: what a runtime manager must satisfy according to the current code and accepted records, and what each OS provides for per-user login start, tray UI and supervision without scheduled tasks, SCM services or elevation. It extends `2026-10-03-runtime-manager-architecture-research`, which already covers why a session-0 Windows service fails. Evidence was gathered on 2026-10-04 at `feature/tui` `50e717e83d` by static reading and web sources. Nothing was executed against a live runtime. Semantic code search was unavailable for part of the sweep, so those parts used targeted reads and grep.

Two features of the evidence matter most. First, every hosting mechanism that satisfies the session and elevation constraints is a per-user process started at sign-in. Second, the runtime currently exposes almost nothing a supervisor can observe. Later sections were corrected on 2026-10-04 after three independent architecture reviews of the first draft ADR. The corrections concern cross-session admission, the single-process installed host, an existing graceful stop path, login-witness false loss, session-end budgets, Linux autostart cgroups, macOS registration APIs and upgrade file locking.

## Findings

### The runtime launch contract is narrow and fully launcher-computable

- The entrypoint is `cadrumo-runtime = cadrumo.entrypoints.runtime.bootstrap:main` (`pyproject.toml:139`). It takes exactly three required arguments, `--storage-root`, `--storage-identity` and `--expected-version`, with no optional flags (`src/cadrumo/entrypoints/runtime/main.py:37-44`). Natively, `cadrumo-runtime.exe` is the shared C interpreter host compiled with the script name fixed in. It is console-subsystem, sits beside `python.exe` and passes all arguments through (`native/cmake/platforms/Windows.cmake:71-81`, `native/CONTRACT.md:104-124`). The manifest is `asInvoker` with Win10+ `supportedOS` (`native/interpreter/windows/host.manifest:1-20`).
- `bootstrap.main` re-executes under `-I` unless the interpreter is already isolated. It strips `PYTHON*`, `LD_*` and `DYLD_*`, and on Windows blocks on the child while forwarding its exit code (`src/cadrumo/entrypoints/runtime/bootstrap.py:17-54`).
  - The native host initializes Python isolated, with `use_environment = 0` and `install_signal_handlers = 1` (`native/interpreter/windows/python.c:20-40`). The re-exec is therefore skipped, and the installed runtime is one process: `cadrumo-runtime.exe` holds the pipe and receives signals.
  - Two processes appear only in development launches through a plain interpreter. There, `subprocess.run` closes inherited handles. On POSIX, `execve` keeps the PID and inherited descriptors.
- The storage root must be absolute (`main.py:154-156`) and comes from Settings and the bucket pointer (`src/cadrumo/core/paths.py:275-296`). The storage identity is not chosen freely. It is `sha256(owner:st_dev:st_ino)` of the resolved root, re-derived by the runtime, which refuses a mismatch with `ROOT_MISMATCH` (`src/cadrumo/adapters/local_runtime/windows.py:36-48`, `posix.py:75-85`, `main.py:100-101`). The expected version must equal the runtime interpreter's installed `cadrumo` version, or the runtime returns `VERSION_MISMATCH` (`main.py:150-153`).
- The desktop host already obtains Settings-derived paths by running `python.exe -I -c <projection>` with `CREATE_NO_WINDOW` (`native/desktop/src-tauri/src/environment.rs:58-176`, `native/desktop/src-tauri/src/python/environment.py`). A Rust launcher can use the same mechanism to read the root and identity from their Python owners, so it doesn't have to re-implement the formula.
- The runtime does not authenticate its launcher. Its only native-parent check guards the runtime's own workers (`src/cadrumo/entrypoints/runtime/worker.py:44-50`, `worker_native_identity.py:20-32`). No console, stdio or working-directory contract exists for the top-level runtime (`windows_process.py:115-116` covers workers only).

### Readiness, exit and shutdown give a supervisor little to observe

- No readiness file or notification exists. Readiness is the listener claiming first-instance ownership (`src/cadrumo/adapters/local_runtime/server.py:92-101`), and a starter can observe it only by completing the verified client handshake (`startup.py`, `runtime_verified_transport.py`).
- Exit codes are coarse. `0` means a clean stop or interrupt. `2` covers every `RuntimeRefusalError` (`ROOT_MISMATCH`, `VERSION_MISMATCH`, `OWNER_BUSY` and others) and also a forced watchdog exit (`main.py:174-193`, `src/cadrumo/entrypoints/runtime/shutdown.py:12-19`). A supervisor cannot tell "already running" from "misconfigured" from "crashed in drain" by exit code alone.
- Single-owner convergence uses `FILE_FLAG_FIRST_PIPE_INSTANCE` on Windows (`windows.py:76-94`) and an exclusive lock in the socket namespace on POSIX (`posix_endpoint.py:192-209`). A second launch fails with `OWNER_BUSY` and does not disturb the first.
- There is no idle timeout. The only timing constants are `DRAIN_SECONDS = 15.0` (`server.py:60`) and the watchdog bound `DRAIN_SECONDS + 2` (`main.py:122`). The process stops on four triggers. The first two are SIGINT and SIGTERM (`main.py:103-104`). The third is an internal connection or cleanup failure (`server_connection_handling.py:148,230,235,240`). The fourth is the loss of every eligible native login witness after one was seen (`src/cadrumo/entrypoints/runtime/profile_connections.py:106-129`). That last trigger is wired only on Windows and Linux; macOS passes no inventory (`main.py:60-67`). A positive locked witness survives, so the screen lock alone does not stop the process. Session and lease expiry force re-authentication of a connection, not process exit (`src/cadrumo/application/user_profile/session_authority_policy.py:125-186`). The operator's report that the runtime "times out" is therefore not explained by an idle timer. Nothing restarts the runtime after any of these exits.
- On Windows, no `WM_ENDSESSION`, console-control or logoff handler exists. A graceful stop is still reachable without any transport request. A `CREATE_NO_WINDOW` child has a hidden console, the host installs Python's signal handlers, and the runtime maps SIGINT to its stop. A same-user launcher can therefore call `AttachConsole(pid)` and then `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` while ignoring the event itself. Workers have their own consoles and are not reached (`windows_process.py:102-123`). On POSIX, SIGTERM does the same. Neither path depends on the runtime's version, and a client confined to Cadrumo's interfaces cannot reach either one. The public owner-stop request was removed by the earlier ADR. Its controls were consent bound to a single connection and boot, a fresh login check, and a separate owner-control connection mode (`2026-10-03-runtime-without-service-manager-scope-removal-audit`).
- Login-witness loss can be a false positive. The runtime polls the logon inventory every 0.5 s, even with no clients (`server.py:191-194`, `profile_connections.py:157-163`). The Windows inventory returns UNKNOWN when it exceeds its 2 s budget, or when any logon session on the machine appears or disappears during the scan (`windows_login.py:165-188`). With no connected client, an UNKNOWN result counts as no eligible login, and the runtime stops (`profile_connections.py:111-128`). An idle runtime can therefore stop on one slow or racing scan, such as after resume, under load, or while another account signs in. Nothing restarts it, which matches the operator's report that it "times out". This was not confirmed by a soak test.
- Session-end budgets are short:
  - Windows ends a windowless process that does not answer `WM_QUERYENDSESSION` within about 5 s, and `ShutdownBlockReasonCreate` does not extend that (https://learn.microsoft.com/windows/win32/shutdown/shutdown-changes-for-windows-vista).
  - A console process that loads user32 does not receive `CTRL_LOGOFF_EVENT` or `CTRL_SHUTDOWN_EVENT` (https://learn.microsoft.com/windows/console/setconsolectrlhandler).
  - `tao` exits the process on `WM_ENDSESSION` and never handles `WM_QUERYENDSESSION` (tao `src/platform_impl/windows/event_loop.rs`).
  - logind delay inhibitors are capped by `InhibitDelayMaxSec`, which defaults to 5 s (https://systemd.io/INHIBITOR_LOCKS/).

  The runtime's 15 s drain plus 2 s watchdog does not fit in any of these. Journals preserve `UNKNOWN` for interrupted work.
- The runtime's own cold start was measured at about 27 s in one installed-fixture run, against a 20 s fixture deadline (`2026-10-03-runtime-without-service-manager-scope-removal-audit`). That record states the figure is not a production performance target.

### Clients already converge on one opener and one refusal

CLI, TUI and MCP open the runtime through `open_installed_runtime_client` (`src/cadrumo/adapters/local_runtime/runtime_client.py:54-101`). It resolves `effective_storage_root()`, derives the endpoint and fails with `RuntimeRefusalCode.UNAVAILABLE` (`src/cadrumo/application/runtime/contracts.py:19`). No client spawns a process. No user-facing remedy text tells the operator how to obtain a runtime. The only guidance is developer documentation (`src/cadrumo/tests/README.md:60-68`). Endpoint naming depends on the resolved storage root, so any launcher and every client must agree on that root. The desktop host passes its own `os.environ` to children (`native/desktop/src-tauri/src/python/environment.py`). A different `CADRUMO_LOCAL_STORAGE_ROOT` in one launch context therefore yields a different endpoint.

### Identity, session and containment constraints on the launch context

- Windows admission requires a primary token with exactly one logon SID and an interactive logon kind (2, 10, 11 or 12), session id above 0, and a visible `WinSta0` associated with that logon SID (`src/cadrumo/adapters/local_runtime/windows_desktop_logon.py:245-348`). It also requires Windows 10 or later as seen through the executable's manifest (`:252`). Peers are not required to share the runtime's session. Transport checks compare only the owner (`TokenUser` SID or uid) and whether the process is alive (`windows_channel.py:47-65`, `posix_channel.py:81`). Login capture deliberately admits same-account peers from any session, including session 0, and binds them to the runtime's own desktop (`windows_login.py:69-75`). An earlier per-session equality check (`a451478df4`) no longer exists. The pipe DACL grants only the owner SID, and the pipe is created first-instance, rejects remote clients and is non-inheritable (`windows.py:64-90`). Clients do not pass `expected_image` in production (`runtime_client.py:54-101`), so a handshake proves the same account and nothing more about the server.
- Multiple sessions for one user share one endpoint, because the pipe name depends only on the owner and the root (`windows.py:47-48`). A second session's launch fails with `OWNER_BUSY`. Interactive prompts such as the Cl@ve browser appear on the desktop of the session that owns the runtime.
- Job membership is inherited on Windows. A desktop app started from a terminal or IDE that owns a kill-on-close job places every descendant in that job, and `CREATE_NO_WINDOW` does not break away. The existing Rust spawn helper kills its child when dropped (`native/application/src/process/mod.rs:60-164`). Escaping requires `CREATE_BREAKAWAY_FROM_JOB` where the job allows it, or a launch dispatched through the Explorer shell.
- No elevation or integrity-level check exists. A UAC-elevated interactive token passes, and only session-0 or non-interactive launches are refused, as a side effect. A launcher has to avoid elevation itself, for example a runtime started from an installer's elevated context.
- On macOS, workers are one-shot launchd jobs in `gui/<uid>` with `LimitLoadToSessionType: Aqua`, and their coalition must differ from the runtime's (`src/cadrumo/adapters/local_runtime/macos_worker_process.py:98-163,786-807`). An Aqua session is required. The runtime itself need not be launchd-started.
- On Linux, workers are transient `systemd-run --user` units (`linux_worker_process.py:262-306`) through `manager_commands.py`, which is live worker containment rather than residual service management. The worker environment is reset with `env -i` and an allow-list that excludes `DISPLAY`, `WAYLAND_DISPLAY` and `XAUTHORITY` (`linux_worker_process.py:238-259`). The headed Cl@ve browser runs in the profile worker (`src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:21`, `worker.py:36`), so headed Cl@ve inside a Linux worker cannot find a display regardless of how the runtime was launched. Secret Service reads `/run/user/<uid>/bus` directly (`linux_secret_bus.py:25-70`).
- Windows workers are placed in a runtime-owned kill-on-close Job Object without breakaway (`windows_process.py:189-233`). Nothing protects the runtime itself from an ancestor's kill-on-close job. A runtime spawned under an IDE terminal, MCP host or Tauri shell job dies with that job, together with all admitted work (`2026-10-03-runtime-manager-architecture-research`, on-demand spawn finding).
- Lock and logout retire attended sessions permanently. The runtime survives a lock, but unlock needs a fresh login capture (`session_authority_core.py:85-97`, `access_contracts.py:287-289`). Only an automation grant with `allow_os_lock` survives a lock (`session_authority_policy.py:117-125`).
- `CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE=1` removes desktop and login admission (`src/cadrumo/adapters/local_runtime/login_policy.py:17-79`, `src/cadrumo/core/config.py:310-322`). A product launcher must never set it.

Predicted Windows launch contexts: HKCU or HKLM `Run`, the Startup folder and Explorer-started processes pass. A deferred MSI custom action fails (session 0). An immediate custom action under an elevated interactive token passes identity checks, which is undesirable. A Tauri or IDE child passes identity checks but inherits the job-kill risk.

### Packaging gives a manager no existing hook

- Installers are one CPack graph: WiX MSI with `CPACK_WIX_INSTALL_SCOPE perMachine` (`native/cmake/distribution/CMakeLists.txt:65`), DEB/RPM/TGZ under `/opt/cadrumo`, and a macOS `.app`/DMG with identity `md.neve.cadrumo` (`native/cmake/Identity.cmake:1-30`). The only per-install registration is a Start-menu shortcut and an `HKLM\Software\<id>\InstallLocation` value (`dev/packaging/native/installation.py:210-241`). No `Run` key, XDG autostart entry, LaunchAgent, `LSUIElement`, Restart Manager or `CloseApplication` authoring exists. `native/CONTRACT.md:347-350` states that the definitions add no automatic launch.
- The Tauri desktop crate enables no tray, single-instance, autostart or updater feature (`native/desktop/src-tauri/Cargo.toml:18`). Its bundler is disabled (`tauri.conf.json.in:21-23`), and it is not yet part of the shipped payload. `native/application` provides spawn, stdio relay and kill-on-drop (`native/application/src/process/mod.rs:60-164`), but no Job Object, process group or restart logic. Job containment exists only in Python (`windows_process.py`). Any new payload binary must be added to the CMake bundle, the hashed package manifest that fails closed on unknown files (`dev/packaging/native/installation.py:36-58`), verification and the signing inventory.

### Accepted records: what binds and what must be reconciled

- These still bind: one owner per OS user and storage root; runtime in the interactive desktop logon; no stored Windows password and no highest-privilege elevation; manager availability, login autostart and unattended authorization as separate capabilities; and unattended agent work only through an enrolled grant (`2026-09-26-mcp-purpose-authentication-adr`, sections "Runtime ownership and connection", "Local transport and platform contract" and "Process containment and custody lifetime"; `2026-09-26-mcp-purpose-authentication-profile-access-adr`, "Four lifetimes").
- These describe the pre-manager state and would need amendment by a manager decision: the flat exclusions in `2026-10-03-runtime-without-service-manager-adr` Constraints (whose Consequences say management is "deferred, not permanently prohibited"), "No service, scheduled task, runtime autostart or storage migration is introduced" in `2026-10-04-application-distribution-adr`, the on-demand-supervisor hypothesis and the open provisioning step 5 in `2026-10-03-application-packaging-adr` (proposed), and the "Runtime lifecycle policy" in `.vaultspec/rules` rule 04.
- No vault record mentions a tray, menu bar, notification area or login item.
- The earlier removal plan `2026-10-03-runtime-without-service-manager-plan` has logged removals for S02-S05 but is open, with failing locale, documentation-coherence and native-endpoint checks in its ledger.

### Per-user login start without tasks, services or elevation

- **Windows.** `HKCU\...\CurrentVersion\Run` and `HKLM\...\Run` are read by Explorer at sign-in in the user's interactive session. Task Manager's Startup apps view toggles them through `StartupApproved` flags without deleting the value (https://www.hexacorn.com/blog/?p=5992). Windows 11 delays Run entries by default (https://ninjaone.com/blog/enable-or-disable-delay-of-running-startup-apps-in-windows-11).
  - A per-machine MSI can write `HKLM\...\Run` for every account, and that entry is removed cleanly at uninstall. Writing `HKCU` reaches only the installing account.
  - A `HKCU` value written by the manager at first run is per-user, but other users' values survive uninstall.
  - A per-user MSI (`ALLUSERS=2`, `MSIINSTALLPERUSER=1`) changes install location and upgrade semantics for the whole product (https://learn.microsoft.com/windows/win32/msi/allusers).
  - Active Setup works but re-runs MSI repair per user (https://learn.microsoft.com/en-us/archive/blogs/alexshev/from-msi-to-wix-part-14-installable-items-registry-keys-and-values).
  - A GUI-subsystem process shows no console. A console-subsystem child started with `CREATE_NO_WINDOW` gets a hidden console. Explorer does not normally place children in a job; PCA jobs allow breakaway (https://learn.microsoft.com/en-us/archive/blogs/alejacma/why-is-my-process-in-a-job-if-i-didnt-put-it-there).
  - WiX `util:CloseApplication` is WiX's own custom action, not Restart Manager. It reaches only top-level windows in the installer's session, times out after 5 s, and prompts for a reboot by default (https://docs.firegiant.com/wix/schema/util/closeapplication/).
  - Windows Installer's Restart Manager integration sends `CTRL_C_EVENT` to each console process it closes, which interrupts workers individually, and cannot close processes in other sessions.
  - In-use files under the package root are replaced at reboot while the others are replaced at once. The bootstrap then refuses mixed hashes (`native/interpreter/bootstrap.py:72-75`), so in-place upgrades with running per-user processes in any session break every client until reboot.
  - `RegisterApplicationRestart` can request a relaunch after a crash (https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-registerapplicationrestart).
  - Windows 11 hides tray icons in the overflow by default.
- **macOS.** `SMAppService.agent(plistName:)` (macOS 13+) registers a bundled LaunchAgent whose plist lives in `Contents/Library/LaunchAgents`. A helper app in `Contents/Library/LoginItems` pairs with `SMAppService.loginItem(identifier:)` instead. launchd starts the agent at registration and at each login. When a launchd job's main process exits, launchd kills its process group unless `AbandonProcessGroup` is set. `KeepAlive` relaunches a user's Quit unless it is conditioned on `SuccessfulExit` (launchd.plist(5)). The user can be required to approve it in Login Items (https://developer.apple.com/documentation/servicemanagement/smappservice). A tray-only helper uses `LSUIElement` and an `NSStatusItem`. Distribution requires consistent signing and notarization (https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution). Behavior of fully unsigned production builds is unverified. Signing credentials are currently unavailable (`2026-10-04-application-distribution-adr`).
- **Linux.** XDG autostart desktop entries in `/etc/xdg/autostart` or `~/.config/autostart` run in the graphical session without an enable step. A packaged `systemd --user` unit needs a per-user `enable`, and `graphical-session.target` is not activated by every desktop (https://third-party-mirror.googlesource.com/systemd/+/refs/heads/master/docs/DESKTOP_ENVIRONMENTS.md). Stock GNOME shows StatusNotifierItem icons only through an extension (https://github.com/Finii/gnome-shell-extension-appindicator), so a no-tray fallback is required. The host can register after autostart has run.
  - systemd's XDG autostart generator turns each entry into a unit with `ExitType=cgroup`, `Restart=no`, `TimeoutStopSec=5s` and `PartOf=graphical-session.target` (systemd `src/xdg-autostart-generator/xdg-autostart-service.c`). A runtime spawned as a child of an autostarted manager therefore shares the manager's cgroup. It is stopped with the manager and killed after 5 s unless it is placed in its own transient `systemd-run --user` unit, as workers already are.

### Tray toolkit and prior art

- `tauri-plugin-autostart` uses the `auto_launch` crate: HKCU `Run` on Windows, a legacy `~/Library/LaunchAgents` plist on macOS rather than `SMAppService`, and a desktop entry on Linux (https://raw.githubusercontent.com/tauri-apps/plugins-workspace/v2/plugins/autostart/src/lib.rs). `tauri-plugin-single-instance` provides a single-instance callback (https://v2.tauri.app/plugin/single-instance/). A windowless manager can avoid a webview entirely with the `tray-icon` crate plus a `tao` or `winit` event loop (https://docs.rs/tray-icon), or `ksni` on Linux (https://docs.rs/ksni). No independent idle-memory benchmark of a windowless Tauri process was found.
- Closest prior art under the same constraints is Ollama's per-user `app.exe` tray, which starts and supervises `ollama serve` from a Startup-folder shortcut (https://github.com/ollama/ollama/issues/13295), and SyncTrayzor supervising `syncthing.exe` per user (https://forum.syncthing.net/t/synctrayzor-windows-host-for-syncthing-installer-auto-start-built-in-browser-tray-icon-folder-watcher-and-more/2011). Docker Desktop and Tailscale put their backends in SCM services, which is the excluded pattern (https://docs.docker.com/desktop/setup/install/windows-permission-requirements/).
- Graceful session-end hooks exist on every platform: `WM_QUERYENDSESSION`/`WM_ENDSESSION` (https://learn.microsoft.com/en-us/windows/win32/shutdown/wm-queryendsession), NSWorkspace power-off notifications, which are unreliable just before shutdown (https://developer.apple.com/forums/thread/751406), and logind `PrepareForShutdown` with inhibitor locks (https://systemd.io/INHIBITOR_LOCKS/). Backoff and crash-loop ceilings are general practice and were not independently sourced.

### Supervisor-relevant runtime facts found during review

- Operation leases last 10 minutes (`src/cadrumo/entrypoints/operation_composition.py:825`). Restart recovery refuses an operation whose lease is still `ACTIVE`, and the supervisor's shutdown wait reports unfinished work as needing recovery rather than settling it (`src/cadrumo/application/operations/_supervisor_reconciliation.py:61-62`, `_supervisor_drain.py:97-125`). A fast exit with work in flight therefore blocks those subjects until their leases expire. `ORPHANED` exists as an operation state (`src/cadrumo/application/operations/models.py:64`).
- Non-worker children are started without console flags. The KDF child uses a plain `subprocess.Popen` (`src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py:53-61`), and the browser installer does likewise (`src/cadrumo/adapters/outbound/browser_runtime/installer.py:38-42`). Both share the runtime's console, so a console Ctrl+C reaches them. Workers get their own consoles.
- Python marks the standard streams inheritable (PEP 446 exempts them). Any child started without redirection inherits them. CPython exits with status `120` when the final flush of `sys.stdout` fails, which collides with the native host's reserved `120`-`124`.
- `SetConsoleCtrlHandler(NULL, TRUE)` makes a process ignore Ctrl+C, and that state is inherited by its children. Handler registrations are not inherited. `CTRL_C_EVENT` reaches every process attached to the console (https://learn.microsoft.com/windows/console/setconsolectrlhandler, https://learn.microsoft.com/windows/console/generateconsolectrlevent).
- logind delay inhibitors cover shutdown and sleep, not logout (https://systemd.io/INHIBITOR_LOCKS/). Restart Manager's query carries `ENDSESSION_CLOSEAPP` (https://learn.microsoft.com/windows/win32/rstmgr/guidelines-for-applications). `WM_ENDSESSION` with `wParam=FALSE` reaches only windows that answered TRUE to the query (https://learn.microsoft.com/windows/win32/shutdown/wm-endsession).
- `systemd-run --scope` runs the command in place, so the caller keeps its standard streams and its child. The user manager must be able to move the pid into the new scope; on cgroup v2 a manager running in a system-owned `session-N.scope` may be refused. `--pipe` runs a service unit that is passed the caller's descriptors, but `systemd-run` then waits as an intermediary (https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html). Neither placement was tested.

### Installer formats constrain side-by-side versions

- **MSI.** CPack's WiX template authors `<MajorUpgrade Schedule="afterInstallInitialize">`, which removes the previous product before installing new files (CMake `Modules/Internal/CPack/WIX.template.in:26-29`). The build uses that template with one per-machine scope and one upgrade code (`native/cmake/distribution/CMakeLists.txt:63-72`). Under a major upgrade, files of a running older version are deleted, or scheduled for deletion at reboot if they are locked. Keeping an in-use version on disk would need one of two things: a product per version with no upgrade relationship plus a version-independent bootstrap product, or authoring beyond the CPack template. CPack produces one scope per MSI and does not author `ALLUSERS=2`/`MSIINSTALLPERUSER` (CMake `Help/cpack_gen/wix.rst`). Per-scope upgrade codes differ (`native/CONTRACT.md:396-398`), so the two scopes do not detect each other. Removing obsolete versions under Program Files needs elevation, which the manager does not have. The behaviour of in-use files under `RemoveExistingProducts` is general Windows Installer knowledge and was not executed here.
- **DEB/RPM.** A single package upgrade removes files the new version no longer ships. Coexisting versions need a package per version plus a metapackage, as kernel packages do, and obsolete versions are then removed by the package manager's own policy.
- **macOS.** A signed bundle is sealed, so adding version directories inside it invalidates the signature. Coexisting versions need separately signed bundles behind a thin launcher.

### Established naming patterns

- One authority for product names exists: `PRODUCT_IDENTITY` (`src/cadrumo/core/product_identity.py:44-56`). Its fields are `display_name` `CADRUMO`, `distribution` `cadrumo`, `cli_executable` `aeat` and `application_id` `md.neve.cadrumo`. `dev/packaging/native/identity.py:37-66` projects it into CMake as `CADRUMO_ID_*`, adding a `.preview`, ` Preview` or `-preview` channel suffix.
- Installer artifacts derive their names from that projection (`dev/packaging/native/installation.py:183-245`):
  - the Linux `{application_id}.desktop` and icon
  - the macOS `CFBundleIdentifier`, `{name}.app`
  - the Windows Start-menu folder and shortcut named by `display_name`, with the AUMID set to `application_id`
  - the `HKLM\Software\{application_id}` key holding `InstallLocation`
- Console entrypoints are kebab-case pyproject scripts declared in `native/package-layout.json` (`cadrumo-runtime`). Rust crates map `native/<name>` to `cadrumo-<name>`. Runtime records pair `.runtime/installation.json` with `installation.lock`. The log file is `cadrumo.log`.
- Platform conventions:
  - Desktop-entry file IDs are reverse-DNS (https://specifications.freedesktop.org/desktop-entry-spec/latest/file-naming.html).
  - A launchd job's `Label` is reverse-DNS, and its plist is named after it (https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
  - A classic Windows desktop app needs an AppUserModelID on its Start-menu shortcut to raise toast notifications (https://learn.microsoft.com/windows/win32/shell/enable-desktop-toast-with-appusermodelid).
- `src/cadrumo/adapters/local_runtime/manager_commands.py` uses "manager" for transient worker-containment commands. That name would read as belonging to a runtime manager.

### What the ADR must settle

- A manager-to-runtime channel for readiness and graceful stop. Exit codes and SIGTERM are insufficient on Windows, and public owner-stop was removed.
- Who registers login start on each platform, how the user opts in or out, and how uninstall removes it.
- Whether the runtime starts eagerly with the manager or on a client's request, and how a client reaches the manager without making the runtime its descendant.
- macOS behavior while signing is unavailable, and Linux behavior without a tray host.
- Upgrade sequencing: stop, replace, restart without an elevated relaunch, and the version-mismatch window.
- The manager's toolkit (webview or native tray) and its relation to `cadrumo.exe`.
- How dev and test builds are kept from registering login start.

Not investigated: whether Explorer places `Run`-key children in a job; whether `StartupApproved` for an `HKLM Run` entry is per user or per machine; macOS coalition behaviour when a launchd job is removed; the elevation context of a `RegisterApplicationRestart` relaunch; the order in which Windows runs `HKLM` and `HKCU` `Run` entries; actual job membership of Claude Desktop, VS Code or Windows Terminal children; AV/EDR reaction to windowless children; Apple Silicon or ARM64 specifics; whether `configured_storage_root()` and `effective_storage_root()` can diverge; whether profile workers write to the shared log file.

## Sources

- `pyproject.toml:139`
- `src/cadrumo/entrypoints/runtime/main.py:37-44`, `:53-67`, `:100-104`, `:122`, `:150-193`
- `src/cadrumo/entrypoints/runtime/bootstrap.py:17-54`
- `src/cadrumo/entrypoints/runtime/shutdown.py:12-62`
- `src/cadrumo/entrypoints/runtime/profile_connections.py:106-129`
- `src/cadrumo/entrypoints/runtime/worker.py:36`, `:44-50`
- `src/cadrumo/entrypoints/runtime/worker_native_identity.py:20-32`
- `src/cadrumo/adapters/local_runtime/server.py:60`, `:92-101`
- `src/cadrumo/adapters/local_runtime/server_connection_handling.py:148-240`
- `src/cadrumo/adapters/local_runtime/windows.py:36-94`
- `src/cadrumo/adapters/local_runtime/posix.py:75-85`
- `src/cadrumo/adapters/local_runtime/posix_endpoint.py:192-209`
- `src/cadrumo/adapters/local_runtime/runtime_client.py:54-101`
- `src/cadrumo/adapters/local_runtime/windows_desktop_logon.py:245-348`
- `src/cadrumo/adapters/local_runtime/windows_login.py:142`, `:212-338`
- `src/cadrumo/adapters/local_runtime/windows_process.py:115-116`, `:189-233`
- `src/cadrumo/adapters/local_runtime/macos_worker_process.py:98-163`, `:786-807`
- `src/cadrumo/adapters/local_runtime/linux_worker_process.py:238-306`
- `src/cadrumo/adapters/local_runtime/linux_secret_bus.py:25-70`
- `src/cadrumo/adapters/local_runtime/login_policy.py:17-79`
- `src/cadrumo/adapters/local_runtime/manager_commands.py`
- `src/cadrumo/adapters/local_runtime/installation.py`
- `src/cadrumo/application/runtime/contracts.py:19`
- `src/cadrumo/application/user_profile/session_authority_policy.py:117-186`
- `src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:21`
- `src/cadrumo/core/config.py:310-322`
- `src/cadrumo/core/paths.py:275-296`
- `src/cadrumo/tests/README.md:60-68`
- `native/CONTRACT.md:104-124`, `:347-350`
- `native/interpreter/windows/host.manifest:1-20`
- `native/cmake/platforms/Windows.cmake:71-81`
- `native/cmake/distribution/CMakeLists.txt:65`
- `native/cmake/Identity.cmake:1-30`
- `native/desktop/src-tauri/Cargo.toml:18`
- `native/desktop/src-tauri/tauri.conf.json.in:21-23`
- `native/desktop/src-tauri/src/environment.rs:58-176`
- `native/desktop/src-tauri/src/python/environment.py`
- `native/application/src/process/mod.rs:60-164`
- `dev/packaging/native/installation.py:36-58`, `:210-241`
- https://www.hexacorn.com/blog/?p=5992
- https://ninjaone.com/blog/enable-or-disable-delay-of-running-startup-apps-in-windows-11
- https://learn.microsoft.com/windows/win32/msi/allusers
- https://learn.microsoft.com/en-us/archive/blogs/alexshev/from-msi-to-wix-part-14-installable-items-registry-keys-and-values
- https://learn.microsoft.com/en-us/archive/blogs/alejacma/why-is-my-process-in-a-job-if-i-didnt-put-it-there
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://docs.firegiant.com/wix/schema/util/closeapplication/
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-registerapplicationrestart
- https://learn.microsoft.com/en-us/windows/win32/shutdown/wm-queryendsession
- https://developer.apple.com/documentation/servicemanagement/smappservice
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/forums/thread/751406
- https://third-party-mirror.googlesource.com/systemd/+/refs/heads/master/docs/DESKTOP_ENVIRONMENTS.md
- https://github.com/Finii/gnome-shell-extension-appindicator
- https://systemd.io/INHIBITOR_LOCKS/
- https://raw.githubusercontent.com/tauri-apps/plugins-workspace/v2/plugins/autostart/src/lib.rs
- https://v2.tauri.app/plugin/single-instance/
- https://docs.rs/tray-icon
- https://docs.rs/ksni
- https://github.com/ollama/ollama/issues/13295
- https://forum.syncthing.net/t/synctrayzor-windows-host-for-syncthing-installer-auto-start-built-in-browser-tray-icon-folder-watcher-and-more/2011
- https://docs.docker.com/desktop/setup/install/windows-permission-requirements/
- Unverified general knowledge: supervision backoff and crash-loop practice; behavior of fully unsigned `SMAppService` builds.
