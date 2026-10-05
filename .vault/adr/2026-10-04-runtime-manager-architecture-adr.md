---
tags:
  - '#adr'
  - '#runtime-manager-architecture'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:1a562ec9e30e6ec50dc82d294d0545402060de11a131b4d6cfac4bed0d08b21c'
related:
  - "[[2026-10-04-runtime-manager-architecture-requirements-research]]"
  - "[[2026-10-03-runtime-manager-architecture-research]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-scope-removal-audit]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
---

# `runtime-manager-architecture` adr: `Per-user runtime manager` | (**status:** `accepted`)

## Problem Statement

The CLI, the TUI and the MCP servers do nothing without a running runtime, and nothing in the product starts one, so an MCP host has nothing to connect to. `2026-10-03-runtime-without-service-manager-adr` removed an unprincipled scheduled-task launcher and deferred launch and management policy to application provisioning.

On 2026-10-04 the operator ruled:
- Runtime management is a definite target.
- The manager owns the runtime's lifecycle. That includes crashes, degradation, and stale or mismatched versions.
- There is no legitimate reason to stop the runtime unless it is defective, and in that case the manager controls it.
- Start at sign-in is on by default. An all-users install applies it to all users; a this-user install applies it to that user only.
- The runtime starts together with the manager.
- Versions install side by side, and the manager owns the cutover.

This record decides the installed topology. The runtime-side contract is `2026-10-04-runtime-manager-architecture-supervisor-contract-adr`.

## Considerations

- The evidence is in `2026-10-04-runtime-manager-architecture-requirements-research`. Sessions, services and tasks are covered in `2026-10-03-runtime-manager-architecture-research`.
- `2026-09-26-mcp-purpose-authentication-adr` binds the runtime to:
  - the user's interactive desktop logon
  - no elevation and no stored password
  - one owner per OS user and storage root
  - separate admission, autostart and authorization
- Today an installed build's storage root falls back to the working directory. `2026-10-04-canonical-environment-adr` (proposed) removes that fallback and gives each channel its own default root.
- Windows job membership is inherited.
- Windows and Linux allow about 5 s at session end, and logind has no logout inhibitor.
- Several sessions of one user share one endpoint, and admission binds every peer to the runtime's own desktop.
- The installer formats as built today do not keep an in-use version on disk across an upgrade:
  - a CPack MSI major upgrade removes the old product first
  - a single DEB/RPM package removes files the new version no longer ships
  - a sealed macOS bundle cannot hold extra versions
- CPack builds one scope per MSI.
- macOS signing is unavailable, and stock GNOME has no tray host.
- `native/platform` owns roots and child environments. It builds only on Windows (`2026-10-03-application-packaging-interpreter-foundation-adr`).

## Considered options

- **A separate per-user manager image, started at sign-in, coupled to the runtime and decoupled from every UI:** chosen. Prior art under the same constraints has this shape.
- **`cadrumo.exe` started as a windowless `--background` instance:** rejected for three reasons:
  - Termination targeting, startup approval and macOS login items identify the process by its image.
  - The process would carry the webview dependency and crash surface for its whole life.
  - macOS needs a separate helper bundle anyway.
  - `cadrumo.exe` with arguments is a headless CLI pass-through, a client that never manages the runtime.
- **The desktop window owns the runtime:** rejected. Closing the window ends service for MCP hosts, and the operator rejects lifecycle coupling.
- **Clients spawn the runtime on demand:** rejected. The runtime would join the client's job and die with it.
- **The runtime starts at sign-in with no manager:** rejected. Nothing would recover crashes, hangs or version changes.
- **Upgrade by stopping and replacing in place:** rejected by the operator.
- **SCM service, SYSTEM broker or scheduled task:** rejected on the 10-03 evidence and by the operator.

## Constraints

**Identity and privilege.**
- The manager is a separate image, `cadrumo-manager`: no webview, GUI subsystem on Windows, `supportedOS` manifest.
- It runs as the signed-in user in that user's interactive session.
- It refuses a full UAC-elevated token, session 0 and non-interactive logons.
- It does not run inside a job it does not own. It tries one escape and otherwise refuses visibly.
- It launches the runtime with an allow-list environment that has no `CADRUMO_*` overrides. It manages only the canonical default root. A root or authority selected by an environment override stays developer-owned and unmanaged.

**Lifecycle ownership.**
- The runtime starts when the manager starts.
- The manager is the only product component that stops the runtime. It does so to:
  - restart after a crash, hang or defect, including a user-chosen Restart remedy
  - quit, which stops both
  - end the session
  - cut over to a new version
- Clients never start, stop or supervise the runtime. Any stop the manager did not initiate is restarted with backoff, unless the session is ending.
- Stop is not an access control; the profile lock is.
- There is no standalone "Stop runtime" in the tray.

**Sessions.**
- There is one runtime per OS user and storage root, and one manager per logon session.
- The session lock and the manager IPC name do not depend on image or scope.
- Only the launching manager, or its successor at cutover, signals the runtime. Adoption and signalling are limited to a runtime in the manager's own session; managers in other sessions only observe through a process handle.
- When the runtime exits, a manager in an active, not disconnected, session may start it. It must first take the per-user start claim. A held claim means "starting elsewhere": no other manager starts a runtime while it is held.
- Quit suppresses automatic starts until the same user signs in again or starts the runtime manually.
- The start claim is a kernel-released lock under the storage root's `.runtime/`, using the custody local lock, so a crashed holder never blocks future starts. The Quit marker is an owner-only record beside it, written with the hardened custody record primitives.
- The Rust manager's implementation of that lock, the record I/O and the record grammar is generated from, or conformance-tested against, the Python owners through the contract generator. It keeps the cross-version stability promise that the stop signals carry.
- Only the managed default root is supervised. Developer and test roots stay developer-owned.

**Authority.**
- The manager holds no profile, session, grant, credential, custody or tax-data authority, and opens no profile connection.
- Approval prompts belong to the TUI. Application sign-in follows `2026-10-04-application-sign-in-adr`; the manager hosts neither.

**Placement and adoption.**
- The runtime is never a descendant of a frontend, and never in a job the manager does not own. A manager crash does not kill it.
- The manager adopts a running runtime only when all of these hold:
  - the server image is a runtime inside a complete installed version
  - it is not elevated
  - its boot record matches the server's pid and creation time and reports native admission
  - its version does not carry this user's failed-version marker
- A foreign runtime is shown to the user and never stopped.

**Login start.**
- The installed package registers login start in its installation scope and removes it on uninstall.
- It is on by default. Each user can turn it off for their own account from the tray. The opt-out lives under the user data root `U`, and the installer never writes user data.
- A machine has at most one scope registered for a given account:
  - the installer refuses a second scope where the other is present
  - if both are nevertheless found, the this-user installation takes precedence: the all-users manager checks for it before taking the session lock and stands down for that account
- Excluded: scheduled tasks, SCM services, system daemons, units that need an enable step the product cannot perform, and pre-login execution.

**Versions.**
- The product never removes or replaces files of a version that a process is using. Removal by an external package manager is detected and handled as a crash followed by cutover.
- A version is complete only once its package manifest verifies, and, when signing exists, its signature too. Versions are ordered by manifest version. Version selection never picks an older version than the newest complete one. Restoring the version that was running after a failed cutover is exempt.
- At most one desktop GUI instance runs per user at a time, across versions, through a single-instance lock owned by the desktop shell.
  - The lock is per user and keyed by the identity family (`md.neve.cadrumo` plus channel), never by install path or version.
  - A second launch hands its activation to the running instance and exits `0`.
  - The headless CLI pass-through (`cadrumo.exe` with arguments) never takes or contends for the lock.
  - Per-user state shared across versions, such as the WebView2 user-data folder, is therefore never opened by two versions at once.
- The manager cuts the runtime over to the newest complete version, and never adopts a runtime of an unknown version. A version whose cutover failed is recorded per user and not retried until a newer version appears or the user chooses Retry.
- Obsolete versions are removed only once unused:
  - for this-user installs, by the manager, through the package manager (for example uninstalling that version's product), never by deleting directories
  - for all-users installs, by the next elevated install, repair or uninstall. That run skips in-use versions and does not close their processes.
- Uninstall never forces down running sessions. It removes the registrations and the version-independent entry point. Running managers detect the entry point's removal and quit gracefully. In-use version directories are removed by delete-at-reboot or by the next elevated maintenance run.

**Prerequisites.** These must be met before the manager ships.
- **Canonical locations.** Storage, log and other locations come from the single canonical, config-driven location definition that the operator directed on 2026-10-04. The Python product, the Rust host and manager, the runtime and the frontend all consume it programmatically, including its process-environment overrides. That definition is `2026-10-04-canonical-environment-adr`. The manager consumes its `strict` profile: it pins the resolved root and never re-resolves it. The manager resolves nothing on its own. The default root must not depend on the working directory, must be the same for every installed version, and must specify creation and permissions. Every surface must resolve the same root from any working directory and any version. The endpoint, the boot record and the cutover all depend on it.
- **Versioned installs.** A versioned-install decision, owned by the distribution workstream, must provide for each format a layout that meets the Versions constraints and a version-independent entry point for login registration and launchers. Examples: an MSI product per version behind a version-independent bootstrap product; per-version DEB/RPM packages behind a metapackage; separately signed version bundles behind a thin macOS launcher. The same decision must provide dual-scope MSI authoring. It must also provide per-OS discovery of the entry point for versioned components such as the desktop, for example a registry value under the package key, a known path or a LaunchServices bundle id. The manager does not ship for a format until a versioned layout for that format is implemented and passes acceptance.

**Naming and authoring.**
- Every manager-facing name derives from `PRODUCT_IDENTITY` (`src/cadrumo/core/product_identity.py`) through the existing identity projection (`dev/packaging/native/identity.py`, `CADRUMO_ID_*`). Channel suffixes apply exactly as they do to the application today. Installer, plist, desktop-entry and manifest templates never hand-write a name.
- Names follow the established package patterns: kebab-case executables beside `cadrumo-runtime`, reverse-DNS component identifiers under `application_id`, and records in `.runtime/` beside `installation.json` and `installation.lock`.
- Each platform artifact follows that platform's documented convention:
  - a freedesktop desktop-file ID
  - a launchd `Label` equal to the plist file name
  - a Windows AppUserModelID on the Start-menu shortcut
- Stable and preview are separate installation families. The canonical location definition gives each channel its own default storage root, so their runtimes, endpoints and `.runtime/` records never contend. If it cannot, an account may install only one channel.
- Every file name says what owns it and what it holds. A record written by the manager carries the `manager-` prefix. A record written by the runtime does not.
- The table under Implementation is normative for names. Paths within it follow the canonical location definition.

**Test boundary.**
- The supervision core is verified against fixture runtimes in isolated synthetic roots, through a test mode that release builds refuse.
- Registration, tray, session end, job escape, cutover and uninstall are verified only in package acceptance on disposable hosts.
- Development and CI machines never receive login registration.

## Implementation

We will ship `cadrumo-manager`, a per-user background process started at sign-in. It starts the runtime immediately and keeps it alive through crashes, hangs, session changes and version cutovers, and it shows background-process state in the notification area or menu bar. Windows ships first. Items marked *hypothesis* may change within the constraints. Detailed values and wording belong to the plan.

**Build.** A new crate, `native/manager`, built by the CMake bundle and covered by manifest, verification and signing. As a Rust image it enters the package through a desktop-style platform-mapping declaration, not the `entrypoints` map, which is reserved for `[project.scripts]`. Like the desktop's `cadrumo.exe`, it sits at the version's package root `P`, so its root is its own directory. It links with the hosts' `/DEPENDENTLOADFLAG:0x800` policy. It launches `P/bin/cadrumo-runtime.exe`, whose `sys.executable` stays `P/python.exe`.
- Roots and the child environment come from the canonical location definition, consumed through `native/platform`.
- The installed Python only derives the storage identity and probes the version.
- The desktop's Settings projection moves to `native/application` after desktop-shell S04–S07 land, or at a cut coordinated with the desktop-shell owner. The fixed Python query and S02's storage-root pin move unchanged.

**Supervision.**
- Start the runtime with `--supervised`.
- Await `ready` while the process is alive, up to a ceiling that tolerates first-run scanning.
- On a stale heartbeat: send `stop`, wait for the drain and the watchdog, then terminate. Effects stay `UNKNOWN` for reconciliation.
- Unexpected exits, hangs and outside stops restart with exponential backoff.
- After a witness-loss exit, restart while the manager's own session is active.
- On `VERSION_MISMATCH`, re-probe and relaunch once. Root and elevation refusals stand down with a reason.
- A crash-loop ceiling leads to a failed state with Retry and Open logs.
- Timers are monotonic. The manager holds a process handle for every supervised runtime (a pidfd on Linux, a kqueue watch on macOS).
- Once session end is observed, automatic restarts are suppressed. Session end is detected from the end-session query, `PrepareForShutdown`, will-power-off, or the manager's own SIGTERM.

**Stop delivery.** Constraint: never use `SetConsoleCtrlHandler(NULL, TRUE)` or `CREATE_NEW_PROCESS_GROUP`.
- *Hypothesis* for Windows: keep a handler that returns TRUE installed permanently. Under a lock, attach to the runtime's console, generate Ctrl+C, wait within a bound for delivery, then detach. Start no process while attached.
- POSIX uses SIGTERM through the held handle.

**Session end** (*hypothesis* for the mechanics):
- *Windows:* the manager's own top-level window procedure handles `WM_QUERYENDSESSION`. It sends `session-end` and blocks for up to about 4 s waiting for the runtime to exit.
  - A later `WM_ENDSESSION` with `wParam=FALSE` restarts the runtime.
  - A Restart Manager `ENDSESSION_CLOSEAPP` from an unrelated installer stops both processes. The manager returns at the next sign-in or desktop dispatch. A `RegisterApplicationRestart` relaunch from an elevated installer context is refused by the manager's elevation check.
- *Linux:* sign-out stops the autostart unit. The manager sends `session-end` on SIGTERM.
- *macOS:* the runtime stops only on power-off or logout. Fast user switching is treated like a lock.

**Platform placement** (*hypothesis* for the mechanisms):
- *Windows:*
  - All-users: a quoted `HKLM\...\Run` value. This-user: `HKCU\...\Run`. Both point at the version-independent entry point.
  - The desktop app starts a missing manager through Explorer shell dispatch.
  - Job escape uses breakaway where allowed, otherwise shell dispatch.
- *Linux:*
  - `/etc/xdg/autostart` or `~/.config/autostart`, matching the scope.
  - The runtime is placed in its own cgroup with `systemd-run --user --scope --quiet` and an explicit stop timeout. A probed fallback to `--pipe` is used where the scope move is refused.
  - The tray waits for a StatusNotifier host.
  - Headed Cl@ve in Linux workers is deferred to its owner.
  - Linux waits for the POSIX `native/platform`.
- *macOS:*
  - `SMAppService.agent` with a bundled plist in `Contents/Library/LaunchAgents`, Aqua session type, relaunch only on unsuccessful exit, process group abandoned.
  - The registered agent is the manager itself, or a launcher that execs the versioned manager, so launchd keeps tracking it.
  - No login start until signing exists. The desktop app opens the manager through LaunchServices.

**Version cutover** (*hypothesis*). The old manager, which still holds the channel, orchestrates:
1. It takes the per-user start claim and holds it until step 4 or step 5 completes. The claim is never transferred.
2. It notifies users with connected attended frontends. It then sends `stop-if-idle`, which fences admissions and stops the runtime only if no operation is in flight. Otherwise admissions reopen and the manager waits.
3. It releases its session lock. It then launches the successor manager as its direct child, keeping a process handle, and passes it a one-time cutover designation. The designation exempts only that successor from the held claim, and only for this cutover. The successor reports its runtime's pid over the manager IPC as soon as it launches it.
4. When the successor reports over the manager IPC that its new-version runtime is ready, the old manager releases the claim and exits.
5. If no report arrives within a bound, the old manager terminates the successor and any runtime it started, retakes the session lock, records the failed version, and restarts the version that was running.

An adopted runtime has no heartbeat, so it cuts over only at the user's Restart or at its next restart.

`retry` from a client only asks the manager to re-evaluate. It never bypasses the idle gate. When the deferral runs out, the result is a user notification, not a forced stop.

**Manager IPC.**
- An endpoint qualified by session and owner, with a closed request set: `reveal`, `retry`, and successor readiness from the designated child manager.
- Both sides verify each other's owner and image.
- Clients name the manager in their `UNAVAILABLE` remedy. The MCP adapter does not send requests automatically.
- The desktop app uses `reveal`.

**Tray.** Shows the runtime and the manager.
- Actions: Restart, Open Cadrumo, Open logs, Start at sign-in, Quit.
- Restart and Quit warn when operations are in flight.
- Strings come from the canonical locale catalogues.

**Storage and logs.**
- The opt-out, the manager's own redacted log and the `.runtime/` records live at locations registered in the storage taxonomy (`2026-08-03-canonical-storage-management-adr`).
- The manager stores runtime reason codes, never raw runtime diagnostics.

**Names.** Stable-channel values are shown. Component identifiers are `{channel application_id}.manager`, for example `md.neve.cadrumo.preview.manager`. The user-facing suffix " Background Services" has a single owner in the identity projection, beside " Preview".

| Item | Name | Pattern followed |
| --- | --- | --- |
| Crate / Cargo package | `native/manager` / `cadrumo-manager` | `native/application` → `cadrumo-application` |
| Executable | `P/cadrumo-manager` (`.exe` on Windows), a root-level native image | root-level `cadrumo.exe`; kebab-case like `cadrumo-runtime` |
| Component identifier | `md.neve.cadrumo.manager` (`{application_id}.manager`) | reverse-DNS under `application_id` |
| User-facing name | "CADRUMO Background Services" (`{display_name} Background Services`) | `display_name` |
| Windows version resource | `FileDescription` = user-facing name, `ProductName` = `display_name` | shown in Task Manager's Startup apps |
| Windows Start-menu shortcut | user-facing name, AUMID = component identifier, in the existing `display_name` folder | existing CADRUMO shortcut and AUMID |
| Windows login entry | `Run` value `md.neve.cadrumo.manager`, quoted path to the version-independent entry point | value named by component identifier |
| Windows entry-point discovery | *hypothesis*: `EntryPoint` value under the existing `Software\md.neve.cadrumo` key, final choice delegated to the versioned-install decision | existing `InstallLocation` value |
| Linux autostart entry | `md.neve.cadrumo.manager.desktop` | existing `md.neve.cadrumo.desktop` |
| macOS LaunchAgent | `Contents/Library/LaunchAgents/md.neve.cadrumo.manager.plist`, `Label` = component identifier | launchd label naming |
| Manager log | `cadrumo-manager.log` beside `cadrumo.log` | `cadrumo.log` |
| Manager preference | `manager-preferences.json` in the canonical configuration location | canonical locations |
| Boot record (runtime) | `.runtime/boot.json` | `.runtime/installation.json` |
| Start claim / Quit / failed versions (manager) | `.runtime/manager-start.lock`, `.runtime/manager-quit.json`, `.runtime/manager-failed-versions.json` | `.runtime/installation.lock` |
| Manager IPC endpoint | `\\.\pipe\cadrumo-manager-{owner and session identity}` (owner-only DACL, first-instance), or a `.sock` in the owner-only runtime socket directory on POSIX | runtime endpoint `cadrumo-runtime-{storage_identity}` |

The user-facing name, and whether it is localized, is a *hypothesis* for the operator to confirm. Tray strings come from the locale catalogues.

**Naming hygiene for the plan.** A routine plan step renames `src/cadrumo/adapters/local_runtime/manager_commands.py`, which only issues worker-containment commands, to `containment_commands.py`. The same step renames `NativeManagerCommand`, `ManagerCommandResult` and `run_manager_command_sync`, and updates `linux_worker_process.py`, `macos_worker_process.py` and their tests atomically. This keeps "manager" unambiguous.

**Acceptance obligations for the plan:**
- fixture supervision: crash, hang, outside stop, witness loss, foreign, stale and forged boot records
- job escape and elevation refusal
- multi-session start claim, handoff and Quit
- session-end settle, cancelled shutdown and teardown restart suppression
- cutover with running processes in several sessions, including rollback, other-session managers held off by the claim, the designated successor's exemption, an old-manager crash between hand-off and readiness (on macOS, whether a child successor survives the agent's exit under launchd)
- coexistence of both scopes
- uninstall residue in both scopes
- no login registration from development builds

Open platform questions are kept in the research record.

## Rationale

The design carries out the operator's rulings: one lifecycle owner, a runtime coupled to it, a sign-in scope that follows the install scope, and cutover owned by the manager. It also satisfies every binding constraint: user identity in the interactive session, no elevation, no tasks or services, a single owner, and independence from every UI and host job.

Letting the old manager orchestrate the cutover keeps the only supervisor channel in charge until the successor is proven. The versioned-install prerequisite keeps the side-by-side ruling honest against what each installer format can actually do. The supervisor contract supplies readiness, hang detection, a stop that works across versions, and identity, without new transport authority. A separate image is what lets the OS, the installer and adoption recognise the manager.

## Consequences

**Benefits:**
- MCP hosts, the CLI and the TUI find a runtime after sign-in.
- Closing a window, terminal or IDE never affects admitted work.
- Crashes, hangs, outside stops, false witness loss and upgrades recover without the user.
- One visible place shows the background processes.

**Accepted costs:**
- One more signed binary.
- Versioned, dual-scope installers that go beyond the CPack defaults.
- Per-platform acceptance on disposable hosts.
- An all-users install keeps a manager and runtime resident for every account that has not opted out.
- Cross-session hosting puts Cl@ve prompts on the owning session's desktop. Logging off the owning session interrupts the other session's admitted work until handoff.
- macOS ships without login start until signing exists, and Linux waits for the POSIX platform crate.
- An adopted runtime lacks hang detection until it next restarts.

**Amendments required once accepted.** Each is proposed together with this record and applied only on approval. The `2026-09-26-mcp-purpose-authentication-adr` amendment text is owned by the supervisor-contract record.
- `2026-10-03-runtime-without-service-manager-adr`, amended. Its removal, development-override and test-lifetime sections stand. Three whole sentences are replaced:
  - "Application bundling, building and provisioning will decide the runtime launch and management policy later."
  - "This decision adds no automatic spawn or replacement manager."
  - "Missing desktop access or an unavailable runtime must be reported, never worked around through OS registration."

  The first two are replaced by: "Management controls on the runtime transport stay excluded. The runtime hosts only the private supervisor contract in `2026-10-04-runtime-manager-architecture-supervisor-contract-adr`. Product lifecycle management, including login registration, belongs to the per-user manager in `2026-10-04-runtime-manager-architecture-adr`."

  The third is replaced by: "Missing desktop access is reported, never bridged through scheduled tasks or services. An unavailable runtime is the per-user manager's to recover."
- `2026-10-04-application-distribution-adr`. Two sentences are replaced:
  - "Use per-machine native package ownership for MSI/DEB/RPM, Applications-folder bundle installation on macOS, and explicit prefix installation for development/archives." becomes "Offer all-users and this-user installation scopes for MSI/DEB/RPM, Applications-folder bundle installation on macOS, and explicit prefix installation for development/archives. Install versions side by side under a version-independent entry point per `2026-10-04-runtime-manager-architecture-adr`."
  - "No service, scheduled task, runtime autostart or storage migration is introduced" becomes "No service, scheduled task or storage migration is introduced. Login start for the runtime manager is registered in the installation scope." Its acceptance evidence includes the manager on disposable hosts.
- `2026-10-03-application-packaging-adr` (proposed). Provisioning step 5 is answered: a dual-scope, versioned install with a per-session supervisor process, and runtime ownership independent of any window. The on-demand-supervisor hypothesis is retired, and the runtime-control UI moves to the manager.
- `2026-10-03-application-packaging-interpreter-foundation-adr`: an extension note authorizing the manager on the platform crate.
- `2026-10-04-desktop-shell-adr` (proposed), S12: the desktop may start a missing manager by shell dispatch and request `reveal`, and never starts the runtime. Approval prompts belong to the TUI. The desktop shell also owns the cross-version GUI single instance defined under Versions. A newer desktop version launched while an older one is open hands its activation to the open window; the user finishes the switch by closing the old window.
- `2026-10-03-application-core-packaging-plan`: its autostart and supervision exclusion is reconciled through the plan verbs.
- Storage taxonomy: register the opt-out, a `LOG_FILE`-style member for `cadrumo-manager.log`, and the `.runtime/` records `boot.json` and `manager-*` together. The existing `runtime` socket member stays distinct.
- Rule 04 "Runtime lifecycle policy" (owned by the operator). Proposed text: "Scheduled tasks, SCM services and system daemons remain prohibited. The installed per-user runtime manager is the sole product supervisor. The desktop may start it by shell dispatch. Other clients never start, stop or supervise the runtime. Development and CI never register login start, and package acceptance runs on disposable hosts."

**Follow-on decisions** (named, not made):
- Restore per-session peer admission, or state in `2026-09-26-mcp-purpose-authentication-profile-access-adr` that attended-session lifetime follows the runtime's desktop when one user has several sessions.
- How MCP-originated approval requests are surfaced when no TUI is open.
- The versioned-install decision required above.

**Reconsider if:**
- a per-user root independent of the working directory cannot be provided
- enterprise deployments need the all-users install to take precedence over a this-user install
- no installer format can meet the Versions constraints
- `HKLM Run` fails under enterprise policy
- `SMAppService` proves unworkable for unsigned or ad-hoc builds
- unattended agent work needs a runtime before any sign-in

Acceptance would establish decision authority only. None of this is implemented.
