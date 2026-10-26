---
tags:
  - '#research'
  - '#runtime-manager-architecture'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:26a82405a0a1b6e90d631a626a0b4225d1e576d20ccd1788db887f4056b68b7a'
related:
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-research]]"
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
---

# `runtime-manager-architecture` research: `Windows runtime host options: service, scheduled task, on-demand agent`

Question (operator, 2026-10-03): At the 2026-10-03 measurement, Cadrumo's CLI/TUI/MCP live operations used a shared local runtime started on Windows through a per-user Task Scheduler task. Should that be replaced by a classic Windows Service with a dedicated binary, and what host satisfies the runtime's requirements without destroying valid implementation? This record frames the option space against requirements derived from code and accepted decisions. The accepted 2026-10-03-runtime-without-service-manager-adr records the decision; this research preserves the earlier option assessment.

Evidence picture: the custody and identity checks in the inspected runtime presumed it runs as the logged-on user, inside that user's interactive desktop logon session. A session-0 Windows Service fails those checks by design and cannot open the visible browser the Cl@ve QR route needs, so a service is only viable as a privileged broker in front of a per-user runtime. The option at the time was how the per-user runtime would be started and supervised, either by a per-user interactive-token task or by an on-demand detached spawn. The defects the operator observed were in how registration was provisioned and cleaned up, not in the logon model.

## Findings

### The runtime exists for custody and a single authority, not for autostart

The accepted topology makes one local runtime the authority for profile-session admission, grant invalidation, isolated execution and process ownership, shared by CLI, TUI and MCP stdio adapters (2026-09-26-mcp-purpose-authentication-adr, Implementation sections "Purpose and ownership" and "Deployment and startup"). Its rejected alternatives were per-command privileged CLI wrappers (no single owner for admission/revocation) and putting authority in each MCP adapter (a conversation cannot own durable work). The guarantees the runtime supplies:

- One owner per OS user and canonical storage root, converged through an OS primitive: a first-instance named pipe on Windows (`src/cadrumo/adapters/local_runtime/windows.py:386`, `OWNER_BUSY` at `:402-408`) and an exclusive `flock` on POSIX (`src/cadrumo/adapters/local_runtime/posix.py:104`).
- Peer- and cohort-verified endpoint with owner-only DACL, peer token checks and a versioned handshake (2026-09-26-mcp-purpose-authentication-adr, "Local transport and platform contract").
- Profile custody in isolated, profile-bound workers that refuse a non-isolated interpreter and a non-native parent (`src/cadrumo/entrypoints/runtime/worker.py:75-82`, `:311-318`), and a sealed `-I` interpreter relaunch at the launch door (`src/cadrumo/entrypoints/runtime/bootstrap.py:347-364`).
- Worker, browser and KDF children contained in runtime-owned kill-on-close Job Objects (`src/cadrumo/adapters/local_runtime/windows_process.py:199-233`; 2026-09-26-mcp-purpose-authentication-adr, "Management surfaces and process containment").
- Admitted work that survives client disconnect, and an MCP adapter that never stops the shared runtime (same ADR and section).

Login autostart is an optional capability the ADR keeps separate from manager availability and unattended authorization ("Manager availability, login autostart and unattended authorization are separate capabilities"). None of the guarantees above is supplied by the OS service manager. The accepted ADR makes the same observation (2026-10-03-runtime-without-service-manager-adr, Considerations).

### The recorded rationale chose a per-user interactive-token task; no Windows Service comparison was recorded

The then-accepted text was: "Windows background startup uses a per-user Task Scheduler logon task with the interactive token, with no stored Windows password or highest-privilege elevation" (2026-09-26-mcp-purpose-authentication-adr, "Local transport and platform contract"). The same ADR's Constraints exclude any "system-wide daemon" and "pre-OS-login execution". Its evidence (2026-09-26-mcp-purpose-authentication-research, "Background ownership follows OS login") cites only `TASK_LOGON_INTERACTIVE_TOKEN` and user LaunchAgents. No vault record weighs a SCM service against the task; a grep of `.vault/` for "windows service", "session 0" and "service control manager" finds only CI-runner and harness records. The Service-versus-task question is therefore open in the record, not settled.

### The current code requires the runtime itself to be in the client's interactive desktop logon

- `current_windows_desktop_logon()` reads the runtime's own token and refuses unless the session id is non-zero, the logon kind is Interactive, RemoteInteractive, CachedInteractive or CachedRemoteInteractive (2, 10, 11, 12), and `WinSta0` is visible and associated with the token's logon SID (`src/cadrumo/adapters/local_runtime/windows_desktop_logon.py:245-334`, checks at `:287-334`).
- Every peer binding requires the peer's owner, authentication id and session to equal the runtime's own witness (`src/cadrumo/adapters/local_runtime/windows_login.py:212-217`, `:234-285`), and each authority observation revalidates it (`:287-338`). The runtime endpoint calls this on each connection (`src/cadrumo/adapters/local_runtime/windows.py:237-242`), and the managed launcher requires positive interactive-login evidence before hosting (`src/cadrumo/entrypoints/runtime/bootstrap.py:48-64`).
- The accepted ADR ties private admission to OS login: "Last eligible OS logout fences private admission and effects" (2026-09-26-mcp-purpose-authentication-adr, "Management surfaces and process containment").

A process in session 0 has session id 0 and a service (5), network (3) or S4U logon, so it fails `_native_token_origin_is_valid` and `_native_token_role_is_valid` by construction. Hosting the runtime in a Windows Service is therefore not a packaging change. It would replace the login-provenance model that the access ADR and these modules implement.

### The secret stores bind to the user's interactive logon session

- The automation secret store calls `CredReadW`/`CredWriteW` directly (`src/cadrumo/adapters/persistence/storage/custody/automation_secret_store.py:90-120`), and profile-session acceleration uses `keyring` (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:190-220`).
- Microsoft documents that `CredWrite` associates the credential with "the logon session of the current token" and fails with `ERROR_NO_SUCH_LOGON_SESSION` because "Network logon sessions do not have an associated credential set" (https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew). DPAPI keys derive from the user's logon credentials (https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
- `TASK_LOGON_S4U` gives "no access to either the network or to encrypted files", and `TASK_LOGON_INTERACTIVE_TOKEN` runs "only in an existing interactive session" (https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).
- This repository already observed the failure mode. The agent harness reaches the host over SSH in session 0 with an S4U token that carries no credentials, so Credential Manager reads fail for the harness only (2026-07-24-profile-login-session-close-honesty-review-audit, finding "environment-blocked-trio-count-and-attribution"). Positive interactive-login and Credential Manager acceptance remain unproven for the same reason (2026-09-26-mcp-purpose-authentication-audit, P03 entries; 2026-09-26-mcp-purpose-authentication-ledger, S10). Microsoft documents the same property for OpenSSH key logons: such a session "doesn't have associated user credentials" (https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement).
- Measured on 2026-10-03: the shell running this research reports `SessionId 0`, `UserInteractive False`. That is the context a service would have.

### The Cl@ve QR route needs a visible window on the user's desktop

Fresh Cl@ve Móvil login opens a headed Playwright window so the operator can scan the QR, and the QR branch forces headed mode (`src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:21-23`, `:704-713`). The runtime owns browser children (2026-09-26-mcp-purpose-authentication-adr, "Management surfaces and process containment"). Microsoft: "Services cannot directly interact with a user as of Windows Vista", and all services run in session 0. The supported bridge is a separate process started with `CreateProcessAsUser` in the user's session, talking to the service over ACL-protected IPC (https://learn.microsoft.com/en-us/windows/win32/services/interactive-services). Obtaining that user token needs `WTSQueryUserToken`, which requires LocalSystem with `SE_TCB_NAME` and is "intended for highly trusted services" (https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsqueryusertoken). A related repo record shows the same boundary: Store activation is refused from an elevated session-0 context and needed a scheduled-task bridge with `LogonType Interactive` (2026-07-21-desktop-capture-harness-adr). Not traced here: whether the current tree already routes Cl@ve fresh login through the runtime worker rather than the frontend process. The ADR requires runtime ownership either way.

### Classic SCM service options and their costs

- LocalSystem service: session 0, no desktop. It must impersonate each pipe client for Credential Manager/DPAPI and launch per-user workers and browsers with `WTSQueryUserToken` plus `CreateProcessAsUser`. That puts a SYSTEM-privileged process in the custody path, contrary to the ADR's "no stored Windows password or highest-privilege elevation". Installation needs `SC_MANAGER_CREATE_SERVICE`, in practice an elevated installer (https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-createservicew).
- Service running as the user account: `CreateService` needs the account name and its password (`lpServiceStartName`, `lpPassword`, same URL), so the Windows password is stored with the SCM. That contradicts "no stored Windows password", may fail for users who sign in with a Microsoft account PIN or Hello and do not know a local password (unverified general knowledge), and still runs in session 0 with a service logon. It does not pass the desktop witness.
- Per-user services (`<name>_LUID` instances created at sign-in): Microsoft documents them only as built-in Windows services whose templates administrators can manage (https://learn.microsoft.com/en-us/windows/application-management/per-user-services-in-windows). `CreateService` documents no user-service type value; `SERVICE_USER_OWN_PROCESS` appears only in that page's keywords. Creating a template needs HKLM writes (admin). It is not a supported third-party contract, and per-user service instances are not documented to run in the interactive window station either.
- Industry pattern when a service is genuinely needed: a narrow privileged helper plus an unprivileged per-user process. Docker Desktop's `com.docker.service` runs as SYSTEM, needs admin at install, exposes a group-ACL'd named pipe and is omitted in per-user installs, while the app runs as the user (https://docs.docker.com/desktop/setup/install/windows-permission-requirements/). OpenSSH for Windows ships `ssh-agent` as a Windows service, disabled by default and enabled from an elevated prompt (https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement). It holds keys but never shows UI.

Result: a Windows Service cannot satisfy "runs in the client's interactive desktop logon with the user's credential set and a visible browser" without a per-user component. The minimal correct split is a SYSTEM broker that only launches a per-user runtime in the user's session, and that per-user runtime still holds all custody. The broker adds supervision and pre-login start, which the accepted ADR excludes. In exchange it adds admin installation, a SYSTEM attack surface and a second binary.

### On-demand spawned user agent with idle exit: what it keeps and loses

- Precedents: `gpg-agent` "is automatically started on demand by gpg, gpgsm, gpgconf, or gpg-connect-agent" (https://www.gnupg.org/documentation/manuals/gnupg/Invoking-GPG_002dAGENT.html). git's credential-cache daemon is started if not running and forgets after a 900-second default timeout (https://git-scm.com/docs/git-credential-cache). 1Password CLI delegates to the user's desktop app with per-terminal authorization (https://developer.1password.com/docs/cli/app-integration-security). None of these is a SCM service. OpenSSH's Windows `ssh-agent` is the counterexample, and it has no UI.
- Kept: everything in the first finding. The unmanaged runtime path already exists, and the proposed ADR cites it (2026-10-03-runtime-without-service-manager-adr, Considerations).
- Lost: login autostart, scheduler-level start without a client, and the outer launcher Job around the host.
- Windows-specific risk not addressed by the proposal's evidence: a child is by default added to its parent's job, and leaves only when the job allows `JOB_OBJECT_LIMIT_BREAKAWAY_OK` and the child is created with `CREATE_BREAKAWAY_FROM_JOB`. Closing a kill-on-close job terminates every member, including nested jobs (https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects). If an MCP host, IDE terminal or TUI host places its children in a kill-on-close job without breakaway, a spawned runtime dies with that host and with it the other clients' admitted work. The proposal's fallback of remaining in the parent job accepts this silently. Which hosts do so was not measured. A task or service start is immune because the scheduler or SCM is the parent. The same page notes that `Win32_Process.Create` children are not associated with the caller's job, a documented but heavier escape.
- Restart-on-crash moves to "next client start reconciles", which the accepted ADR already requires to be safe ("restart recovery cannot depend on graceful callbacks").

### Frontend-owned or in-process runtime

Rejected on the record. It breaks the single shared owner across CLI/TUI/MCP and admitted-work survival, and the in-process variant removes the sealed interpreter and custody boundary (2026-10-03-runtime-without-service-manager-adr, Considered options; 2026-09-26-mcp-purpose-authentication-adr, Considered options). No new evidence changes that.

### Linux and macOS per-user managers are idiomatic

A systemd user service, with optional socket activation, and a per-user LaunchAgent limited to the `Aqua` session type are the platforms' standard per-user supervision mechanisms (https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html; https://www.freedesktop.org/software/systemd/man/latest/systemd.socket.html). GnuPG ships systemd user socket examples but now calls systemd-based launching deprecated, citing races with its own on-demand start lock (https://dev.gnupg.org/T6336). That is a caution against running a manager and on-demand spawn side by side without one ownership primitive. Cadrumo's pipe/`flock` ownership already covers the race. macOS profile workers currently refuse `CONTAINMENT_UNAVAILABLE` (`src/cadrumo/adapters/local_runtime/profile_worker.py:179-180`), independent of the host choice.

### Requirements and options matrix

Requirements on Windows, derived from the findings above. R1: run as the user, in the client's interactive logon session (desktop witness, Credential Manager, DPAPI). R2: visible browser on the user's desktop. R3: no admin rights and no stored Windows password. R4: one owner per storage root. R5: start on demand from any client. R6: survive the launching frontend and its job. R7: crash recovery. R8: optional login autostart. R9: clean uninstall with no residue from tests. R10: multiple profiles in one runtime.

| Option | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCM service, LocalSystem | no (session 0; impersonation re-architecture) | only via CreateProcessAsUser bridge | no | yes | yes | yes | SCM recovery | yes, pre-login (excluded by ADR) | installer-owned | yes |
| SCM service as the user | no (service logon, session 0) | no | no (stores password) | yes | yes | yes | yes | yes | installer-owned | yes |
| SYSTEM broker plus per-user runtime | yes (runtime) | yes | no (admin install) | yes | yes | yes | yes | yes | installer-owned | yes |
| Per-user service template | unsupported for third parties | no | no | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| Interactive-token task (historical) | yes | yes | yes | yes | yes once provisioned | yes | launcher retries | yes | missing then (fixable) | yes |
| On-demand detached spawn with idle exit | yes | yes | yes | yes | yes, no provisioning | at risk under kill-on-close host jobs | next start reconciles | no | trivial | yes |
| Frontend-owned or in-process | yes | yes | yes | no | yes | no | no | no | trivial | partial |

### Questions considered by the ADR

- Whether login autostart and unattended agent work while no Cadrumo client is running are product requirements. Only the task and the service variants provide them; on-demand spawn does not.
- Whether R6 is required against hosts that place children in kill-on-close jobs. If so, on-demand spawn alone is insufficient on Windows and needs a non-inheriting start (task, WMI, or a broker).
- If the task is kept: provisioning on first use without a separate verb, a vendor task folder, a single task per user rather than per storage root, a product uninstall verb, and test isolation so tests cannot register real tasks. A hybrid is possible, where on-demand spawn is the default and the task is an opt-in for autostart.
- Whether a signed, windowless native host binary is wanted for identity and no-console behaviour. That question is independent of service-versus-task.
- Code that stays valid under every option except the frontend-owned one: endpoint DACL and peer verification (`src/cadrumo/adapters/local_runtime/windows.py`), desktop-logon and login-provenance checks (`windows_desktop_logon.py`, `windows_login.py`), Job containment (`windows_process.py`), sealed bootstrap and worker isolation (`src/cadrumo/entrypoints/runtime/bootstrap.py:347-364`, `worker.py`), single-owner convergence and the startup readiness loop (`src/cadrumo/adapters/local_runtime/startup.py:152-200`). The former manager adapter was option-specific; an SCM service would also require different login-provenance checks.

Not investigated: actual job membership of Claude Desktop, VS Code or Windows Terminal children; console-window visibility of the current task; Windows Hello or PIN-only accounts with service logon; whether Cl@ve fresh login currently executes inside the runtime worker.

## Sources

- `src/cadrumo/adapters/local_runtime/windows_desktop_logon.py:245-334`
- `src/cadrumo/adapters/local_runtime/windows_login.py:212-338`
- `src/cadrumo/adapters/local_runtime/windows.py:237-242`, `:386-408`
- `src/cadrumo/adapters/local_runtime/posix.py:104`
- `src/cadrumo/adapters/local_runtime/windows_process.py:199-233`
- `src/cadrumo/adapters/local_runtime/startup.py:152-200`
- `src/cadrumo/adapters/local_runtime/profile_worker.py:179-180`
- `src/cadrumo/adapters/persistence/storage/custody/automation_secret_store.py:90-120`
- `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:190-220`
- `src/cadrumo/adapters/outbound/aeat/auth/clave_movil.py:21-23`, `:704-713`
- `src/cadrumo/entrypoints/runtime/bootstrap.py:48-68`, `:137`, `:347-418`
- `src/cadrumo/entrypoints/runtime/worker.py:75-82`, `:311-318`
- `dev/agent_eval/tests/test_runtime_automation_management_parity.py:754`
- `pyproject.toml:139`
- https://learn.microsoft.com/en-us/windows/win32/services/interactive-services
- https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsqueryusertoken
- https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-createservicew
- https://learn.microsoft.com/en-us/windows/application-management/per-user-services-in-windows
- https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type
- https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-hidden
- https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
- https://docs.docker.com/desktop/setup/install/windows-permission-requirements/
- https://www.gnupg.org/documentation/manuals/gnupg/Invoking-GPG_002dAGENT.html
- https://dev.gnupg.org/T6336
- https://git-scm.com/docs/git-credential-cache
- https://developer.1password.com/docs/cli/app-integration-security
- https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
- https://www.freedesktop.org/software/systemd/man/latest/systemd.socket.html
- Local read-only measurement, 2026-10-03: `Get-ScheduledTask` (OneDrive and Edge task principals; 2 `cadrumo-runtime-*` tasks) and the current process `SessionId 0`, `UserInteractive False`.
- Unverified general knowledge: that PIN-only or Microsoft-account users may not know a local password usable as a service logon.
