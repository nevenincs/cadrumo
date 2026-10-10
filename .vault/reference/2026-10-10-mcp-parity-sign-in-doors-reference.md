---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:9d602878b3da623fe9394e29e8848f3b467f87c8a82ca764181fce629ebd89ad'
related: []
---
# `mcp-parity` reference: `sign in doors`

This reference records how each Cadrumo frontend obtains a session for a profile, what that session may do, how long it lives, and what the runtime pushes back. Every locator below is relative to the root of this repository, on branch `feature/tui` at commit `85f84a2680`, read on 2026-10-10 by static analysis with nothing executed. The tree carried uncommitted changes by another session; of the files cited here, only `src/cadrumo/application/user_profile/access_contracts.py` (hunks near lines 290-320) and `src/cadrumo/entrypoints/runtime/profile_host.py` (line 572) differ from the commit in Python, and neither hunk touches a cited line. The desktop-shell files in the last section are uncommitted work and may change. The accepted record is cited by path with its status.

## Summary

No frontend keeps login state. The runtime holds every session; a frontend asks it to log in for one exact profile and keeps only its own session identifier. The runtime accepts three methods, and accepts two of them (`password`, `receipt`) only from the command line and the terminal interface. The command line and the terminal interface can therefore use the shared sign-in; the MCP adapter authenticates with a credential reference only and has no code path that sends the other two methods. A session made from the shared sign-in has a larger ceiling than a session made from a key, is checked as `human` by the human gate whatever the frontend, and is bounded by the sign-in deadlines instead of a five-minute lease. Several gates nevertheless stay keyed on frontend and are listed in a table below.

### 1. Where login state lives and the three methods

The login request names a profile, a method, a frontend, an optional narrowing scope and a flag asking the runtime to persist the shared sign-in (`src/cadrumo/application/runtime/profile_access.py:73-83`). The methods are `password`, `receipt` (resume the shared sign-in) and `api_key`.

- The client holds only `_session_id`, cleared when the runtime reports the session retired (`src/cadrumo/adapters/local_runtime/frontend_client.py:103`, `:112-129`). The client builds the login request from profile, frontend, method and the persist flag, and never sets `scope` (`:233-241`).
- Resuming presents a proof read from the OS keychain on one verified frame. The client never unwraps, extends or deletes the shared sign-in; the runtime verifies the proof against the connection's OS login and the current sign-in generation and deletes a receipt it refuses (`src/cadrumo/adapters/local_runtime/frontend_client.py:283-308`; `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:31-39`).
- The runtime refuses `password` and `receipt` from any frontend other than the command line and the terminal interface, as an invalid frame; it refuses a narrowing `scope` on those two methods; and it refuses the persist flag unless the method is `password` from one of those two frontends (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:132-145`). `api_key` has no frontend condition there.
- For all three methods the runtime requires an active OS login, and for `password` and `receipt` an unlocked one (`:180-182`). A connection that already holds a valid session refuses a second login as a conflict, and a connection cannot change frontend (`:156-162`, `:193-210`; `src/cadrumo/adapters/local_runtime/frontend_client.py:230-231`).
- The shared sign-in is written when a `password` login asks to persist it: by `config login` (`src/cadrumo/entrypoints/cli/config/custody.py:217`) and by a checkbox on the terminal-interface login screen (`src/cadrumo/entrypoints/tui/secret/runtime_login.py:216-218`). The runtime mints it after publishing the human session (`src/cadrumo/application/user_profile/session_authority_admission.py:398`, `:404-427`).

### 2. Command line

Every runtime-route command opens a connection for the exact profile with the command-line frontend and authenticates before the command runs (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:149-185`). No state is carried between invocations except the shared sign-in and the stored credential.

- With a credential reference the command opens a credential client instead and skips the authentication step (`:168-177`). That client requires the `api_key` method and no secrets-channel selection (`:223-228`), reads the key from the per-user OS secret store by reference and logs in with `api_key` (`src/cadrumo/adapters/local_runtime/runtime_credentials.py:63-72`, `:75-118`).
- Otherwise `_authenticate` takes, in order, an API key from a secrets channel, a password from a secrets channel, or the console path (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:107-146`).
- The console condition is `terminal_can_prompt_for_secrets()`. When it is false and no secrets channel was given, the command refuses with a missing-channel verdict and never tries to resume (`:125-130`). When it is true, the command calls `resume_receipt` (`:132`); if the keyring is unavailable it falls back to a password prompt (`:135-138`), and any other refusal becomes a policy verdict (`:140-146`).
- A password login in this path does not ask to persist the sign-in; when none was persisted the command stages a notice (`:66-86`).
- `config login` tries `resume_receipt` first when a terminal can prompt and no secrets channel was given, then falls back to a password with the persist flag set (`src/cadrumo/entrypoints/cli/config/custody.py:195-236`).

### 3. Terminal interface

The login screen owns opening and proving one connection, and the authenticated client is kept for the lifetime of the interface; the scope that retains it "never opens local custody" (`src/cadrumo/entrypoints/tui/runtime_admission.py:72-110`). The screen offers four methods: password, API key, API reference and receipt (`src/cadrumo/entrypoints/tui/secret/runtime_login_contracts.py:14-20`; `src/cadrumo/entrypoints/tui/secret/runtime_login_attempt.py:97-153`). The connection is opened with the terminal-interface frontend (`src/cadrumo/entrypoints/tui/installed_session.py:97-111`). When the accepted method is API key or API reference, the interface starts a restricted session application instead of the full workbench root (`:132-145`, `:170-175`).

### 4. MCP adapter and the divergence

The MCP entry point takes `--profile-id` and an optional `--credential-reference`; no secret is an argument (`src/cadrumo_harness/mcp/main.py:21-22`). `serve` builds an adapter with no client, tries the reference once if given, and keeps serving if that fails, storing the denial code (`src/cadrumo_harness/mcp/server.py:46-68`; `src/cadrumo_harness/mcp/runtime_adapter.py:82-88`). The `authenticate` tool opens a credential client with the MCP frontend, requires an exact admitted status, swaps it in and retires the previous client (`:115-126`, `:333-347`).

- The admission check requires a live automation grant: `status_admits_session(..., requires_automation_grant=True)` (`src/cadrumo_harness/mcp/runtime_admission.py:42-55`). The client must also carry the MCP frontend and the exact profile (`:16-19`).
- Enrollment and grant change use a second connection: a fresh unauthenticated MCP connection for a first enrollment, or a credential client for a grant change (`src/cadrumo_harness/mcp/runtime_adapter.py:255-271`). A grant change requires the connection to be an admitted key session of that exact profile and frontend (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:219-237`).
- No file under `src/cadrumo_harness` calls `login_password`, `login_api_key`, `resume_receipt` or `sign_in_status`.
- The exact gate that refuses the shared sign-in from MCP is `_validate_login_request`: a `password` or `receipt` login whose frontend is not the command line or the terminal interface raises `RuntimeRefusalCode.INVALID_FRAME` (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:136-140`). The adapter's own admission check is a second, independent condition (`src/cadrumo_harness/mcp/runtime_admission.py:49-52`).

The divergence is therefore two conditions stacked: the runtime does not accept the human methods from the MCP frontend, and the adapter accepts only a session that is backed by an automation grant.

### 5. What the two session kinds hold

The session kinds are `human`, `attended` and `api_key`, defined independent of frontend (`src/cadrumo/application/user_profile/access_contracts.py:152-157`). A shared-sign-in login (password or receipt) yields `human`; an `api_key` login yields `api_key`; `attended` is built only by `delegate` (`src/cadrumo/application/user_profile/session_authority_admission.py:562`).

| Aspect | Session from the shared sign-in | Session from a key |
| --- | --- | --- |
| Ceiling: operations | All registered definitions (`src/cadrumo/entrypoints/runtime/profile_host.py:456-457`) | Same ceiling, then intersected with the grant scope (`src/cadrumo/application/user_profile/session_authority_admission.py:184`) |
| Ceiling: actions | All access actions (`profile_host.py:458`) | Same, then intersected with the grant |
| Ceiling: disclosures | Every result, review and workspace-refresh schema in every category for its own destination, plus operation metadata (`profile_host.py:433-455`) | Only the disclosures of the grants held by its client (`profile_host.py:425-432`) |
| Right to delegate | Set (`profile_host.py:462`) | Set in the ceiling, narrowed by the grant |
| Grant in the effective scope | Not intersected: the grant scope is added only when the kind is not human (`src/cadrumo/application/user_profile/operation_access_policy.py:144-147`) | Intersected |
| Session scope at admission | The profile ceiling (`session_authority_admission.py:369`) | Requested scope, grant scope and profile ceiling (`:184`) |
| `requires_human` operations | Pass the human gate | Refused as `HUMAN_AUTHORITY_REQUIRED` |

The human gate compares session kind only: `policy.requires_human and session.kind is not SessionKind.HUMAN` (`src/cadrumo/application/user_profile/operation_access_policy.py:175-176`). The declared frontend list is checked on the next line (`:177-178`), independently of kind. An attended session fails the human gate, as a key session does. Wire handlers for own-session lock, lock of another session and human sign-out contain no frontend comparison; they test session kind (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:182-224`; `src/cadrumo/application/user_profile/access_administration.py:205-214`; `src/cadrumo/application/user_profile/session_authority_access.py:115-122`).

### 6. Gates still keyed on frontend

The declared list is each definition's `permitted_frontends`, checked at `src/cadrumo/application/user_profile/operation_access_policy.py:177-178`, at `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:241` and `:263`, and through `require_declared_frontend_and_action` for definitions whose resolver calls it (`src/cadrumo/application/operations/access_resolution.py:160-170`). A search of non-test source for comparisons of a frontend against literals found the following gates besides that list.

| Gate | Frontends allowed | Locator |
| --- | --- | --- |
| Shared sign-in login, scope and persist flag | CLI, TUI | `src/cadrumo/entrypoints/runtime/profile_connection_admission.py:132-145` |
| Operation secret delivery | CLI, TUI | `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:89-90`; `src/cadrumo/entrypoints/runtime/operation_host.py:385-392`; client side `src/cadrumo/adapters/local_runtime/frontend_client.py:315-316` |
| Access management door (deny, inventory, recovery, resume) | CLI, TUI, live human, unlocked OS login | `src/cadrumo/entrypoints/runtime/profile_connection_access.py:65-72`, `:95` |
| Password reset prepare | CLI, TUI | `src/cadrumo/entrypoints/runtime/bootstrap_reset.py:57` |
| Profile delete | CLI, TUI | `src/cadrumo/entrypoints/runtime/bootstrap_delete.py:91` |
| Workbench generation, with a human lease | CLI, TUI | `src/cadrumo/entrypoints/runtime/operation_authority.py:100-117` |
| Automation inventory and decision clients | CLI, TUI | `src/cadrumo/adapters/local_runtime/automation_inventory.py:171`; `src/cadrumo/adapters/local_runtime/automation_decision.py:241` |
| Lifecycle notices requested in the hello | CLI, TUI | `src/cadrumo/adapters/local_runtime/runtime_client.py:78-80` |
| MCP query read resolver | MCP | `src/cadrumo/application/modelo/mcp_query_operation.py:226` |
| Workstation check resolver | CLI | `src/cadrumo/application/workstation_check_operation.py:302` |
| Quickfile resolver | CLI | `src/cadrumo/application/modelo/quickfile_operation.py:354` |
| Ledger bulk classify resolver | CLI | `src/cadrumo/application/ledger/bulk_classify_operation.py:248` |
| Ledger evidence ingestion resolver | CLI | `src/cadrumo/application/ledger/evidence_ingestion_operation.py:269` |
| Ledger export resolver | CLI, TUI | `src/cadrumo/application/ledger/export_operation.py:236` |
| Certificate source resolver | CLI, TUI | `src/cadrumo/application/auth/certificate_source_operation.py:258-259` |

Roughly forty further sites in the terminal-interface and command-line modules compare a client's own frontend to its expected value before using it, for example `src/cadrumo/entrypoints/tui/runtime_session.py:93` and `src/cadrumo/entrypoints/cli/runtime_profile_binding.py:111`. They assert the identity of the caller's own client object and were not enumerated.

### 7. Lifetimes

| | Human session | Key session |
| --- | --- | --- |
| Expiry | `min(idle_deadline, absolute_deadline)` of the sign-in at admission (`session_authority_admission.py:346`, `:371`) | `min(now + 5 minutes, grant expiry, key expiry)` (`:172`); the five-minute cap is `src/cadrumo/application/user_profile/access_contracts.py:28` and a non-human session longer than it fails validation (`:179-180`) |
| Human sign-out | Retired (`src/cadrumo/application/user_profile/session_authority_lifecycle.py:35-52`) | Kept: "API-key grants and sessions retain their policy" (`:44`) |
| Lock this profile everywhere | Retired | Retired (denial kind `PROFILE_LOCK` retires every session, `:79-86`) |
| Revoke all automation | Kept | Retired (kind `ALL` retires non-human sessions, `:83`) |
| Revoke one key or grant | Not applicable | Retired by key or grant id (`:84-85`) |
| OS lock | Not traced in code | Refused unless the grant allows it (`src/cadrumo/application/user_profile/session_authority_policy.py:150-155`) |
| Connection close | Retired (`session_authority_lifecycle.py:54-58`) | Retired |
| Profile lock generation, runtime boot or custody change | Retired by evaluation (`session_authority_policy.py:54-68`) | Same |

Expired or ineligible sessions are fenced by a host sweep that runs without a frontend asking (`session_authority_lifecycle.py:60-68`; `src/cadrumo/application/user_profile/session_authority_core.py:249-272`). A failed evaluation retires the session and emits an event (`session_authority_core.py:137-158`).

- Refresh exists only for a root key session. `refresh_api_key` returns `PARENT_INVALID` for any session that is not a key session or has a parent (`session_authority_admission.py:453-454`), and the worker's custody refuses the same (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:97-103`). It keeps the session id, recomputes expiry from now and retires descendants (`session_authority_admission.py:441`, `:470-481`).
- The wire request `session_refresh` and the client method `refresh_api_key` exist (`src/cadrumo/application/runtime/profile_access.py:90`; `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:198`, `:248-258`; `src/cadrumo/adapters/local_runtime/frontend_client.py:385-387`). A search of the repository's Python found calls only in tests.
- Delegation: `delegate` has no caller outside tests, and no request in the runtime union carries it (`session_authority_admission.py:483-507`; `profile_access.py:97-112`). The custody half exists: `share` attaches a child that may not outlive its parent, may not widen its scope and must share its originating login (`profile_worker_custody.py:80-95`).
- A lapsed lease makes `custody.require` refuse at the next guard (`profile_worker_custody.py:117-125`). An operation is authorized against the lease of the session that submitted it (`src/cadrumo/entrypoints/runtime/operation_authority.py:266-276`).
- The idle deadline of the shared sign-in is described as sliding in the receipt's design note (`acceleration_receipt.py:20-22`); who slides it is not traced.

### 8. Authorization sections and the worker

Every held authorization section has a deadline: the sooner of the session's expiry and 30 seconds (`src/cadrumo/application/runtime/worker_authorization.py:33`; `src/cadrumo/adapters/local_runtime/worker_authorization.py:311-316`). A section with no time left is refused as `SESSION_EXPIRED` (`:314-315`). The permit write and each instruction read inside the section take that deadline (`:157-162`, `:245`). A failure inside the section calls `_contain()` on the owned worker job, because a missing or ambiguous release cannot prove the effect body stopped (`:163-172`). The custody states the same: "the runtime contains the worker if the permit expires before release" (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:131-134`).

There is one worker per profile: one host per profile is stored (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:105`) and each host owns one session owner built on one worker identity (`src/cadrumo/entrypoints/runtime/profile_host.py:185-186`, `:216-223`). A contained worker is therefore the worker of every session on that profile; what happens to those sessions afterwards was not traced.

### 9. What the runtime pushes and the public sign-in status

Session retirement is pushed to the connection that owned the lease. The kinds are `revoked`, `signed_out`, `profile_locked` and `custody_changed` (`src/cadrumo/application/user_profile/session_retirement.py:10-16`). The default is `revoked`; the reason `PROFILE_LOCKED` or `CUSTODY_CHANGED` selects the matching kind, and human sign-out passes `signed_out` (`src/cadrumo/application/user_profile/session_authority_core.py:183-217`; `session_authority_lifecycle.py:35-40`). The frame carries session, connection and profile ids, the kind and the denial reason (`src/cadrumo/application/runtime/session_events.py:13-26`). Queues are per connection, registered at handshake for every frontend, bounded at 64 events, and an overflow closes the stream at its next turn (`src/cadrumo/entrypoints/runtime/session_events.py:11`, `:23-43`, `:76-87`).

- Every client subscribes to these events at login (`frontend_client.py:259-262`) and clears its session id (`:112-129`). The MCP adapter registers no receiver; a retired lease shows up as `authentication_required` on its next call (`src/cadrumo/adapters/local_runtime/frontend_operation_client.py:83-86`).
- The only lifecycle notice is `upgrade_pending` (`session_events.py:35-44`). It is queued only for a connection whose hello requested notices (`src/cadrumo/entrypoints/runtime/session_events.py:45-48`), and the hello requests them only for the command line and the terminal interface (`runtime_client.py:78-80`).
- The public sign-in status request carries a request id and a profile id and no frontend (`src/cadrumo/application/runtime/sign_in.py:44-50`). The runtime checks only that the peer's OS owner matches, admits no session and opens no worker (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:288-304`). The reply holds presence (`present`, `absent`, `unknown`) and, when present, both deadlines, with the idle deadline not after the absolute one; it holds no secret (`sign_in.py:15-41`). The command line uses it in `config sign-in-status` (`src/cadrumo/entrypoints/cli/config/custody.py:315`).

### 10. Command-line leaves that run with no runtime session

The command-line root callback skips the session open for verbs whose path matches a declared exemption, and also for a bare invocation (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py:357-380`). The registry has 24 records, each with a closed criterion, matched by path prefix; a prefix record names its permitted descendants (`:133-354`). The records are:

- First run and recovery: `config profile create`, `config profile archive import`, `config reset` (descendants `resume`, `start`, `status`), `config repair` (six descendants), `config storage` (`check`, `init`, `list`, `reclaim`, `view`).
- Session doors: `config login`, `config logout`. Discovery and deletion: `config profile list`, `config profile delete`.
- Bundled catalogues: `app ledger categories`, `app live portals list`, `app live portals view`, `config auth providers`, `config auth apoderado scopes list`, and `app modelo` `list`, `describe`, `casilla`, `casillas`, `formulas`, `support-matrix`.
- Operator-supplied artefacts: `app modelo review-package` `verify`, `verify-signature`, `verify-receipt`, and `config profile archive inspect`.

The notes in the registry are unverified prose by the registry's own statement (`:56-61`). The reset handler is the read example. `config reset start` calls `start_config_reset` in process with ports from the command context and no runtime client (`src/cadrumo/entrypoints/cli/config/reset_cli.py:77-102`). The call lists every profile bucket and adds the pointer's bucket, takes the deletion locks for all of them, writes the journal and rolls forward (`src/cadrumo/application/config_reset.py:84-150`). Some exempt verbs open their own runtime client inside the handler, as `config login` does (`custody.py:195-236`).

### 11. The desktop shell's sign-in observation (uncommitted)

The shell holds no runtime connection. A host-side observer re-reads the public status every 2 seconds, or sooner when woken, by running the command-line `config sign-in-status` leaf, and pushes a frame to the window only when the status or the error changed (`native/desktop/src-tauri/src/shell/sign_in/observation.rs:1-2`, `:59-86`, `:90-124`; `native/desktop/src-tauri/src/shell/sign_in/mod.rs:51-56`, `:121-127`, and the argument assertion at `:617-620`). The file is untracked. It publishes `sign-in-state` or `sign-in-observation-failed` frames with a revision and sends them over one subscription channel (`observation.rs:14-25`, `:167-170`).

In the window, one function maps status to an account phase (`no-host`, `checking`, `starting`, `unsupported`, `signed-in`, `in-tui`, `services-down`, `unknown`, `no-profile`, `signed-out`) and the gated phases are `checking`, `starting`, `services-down`, `unknown`, `no-profile` and `signed-out` (`native/desktop/frontend/src/shell/signIn.ts:41-94`, `:62-69`). The dialog is offered by state: `open={account.gated && !signInDismissed}` (`native/desktop/frontend/src/App.tsx:2075-2077`), and profile choice is offered only in `signed-out` or `no-profile` (`signIn.ts:446`). A password can be submitted only in `signed-out` or `unknown` (`:107-115`). Pressing a sign-in control calls `askSignIn`, which only clears the dismissal flag; it cannot open the dialog while the phase is not gated (`App.tsx:323-330`, `:2077`). The account object exposes no function that opens the dialog (`signIn.ts:581-640`).

### 12. Two frontends on one profile

Each connection has its own session and its own frontend, and both use the one host and worker for the profile (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:105`, `:147-168`). Resuming does not consume the shared sign-in (`frontend_client.py:283-292`), so both can resume it. A second submission of the same definition on the same subject is refused while the first is unsettled (`src/cadrumo/application/operations/errors.py:31-42`). Ownership rules:

- Starting an operation, delivering its secret and responding to a review stay with the submitting session (`src/cadrumo/entrypoints/runtime/operation_host.py:317-320`, `:383-392`, `:525-545`; `src/cadrumo/entrypoints/runtime/operation_authority.py:525-540`).
- Observing and reading an admitted operation are described as caller-independent, still bounded by the reader's own disclosure scope (`src/cadrumo/application/user_profile/profile_operation_access.py:80-86`); the workbench projection is released only to the generating human session (`operation_host.py:461-468`).

### 13. The accepted profile-access record

The record is `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md`, status `accepted` (heading line 20), amended 2026-10-04. The sentences that bear on which principal an agent uses:

- `:72` "Attended agent access | Explicit delegation tied to a valid human authorization | Access ending no later than that authorization".
- `:73` "Unattended agent, machine CLI or restricted TUI login | Active enrolled API key/grant plus available protected unlock capability | Fresh bounded session for the exact profile".
- `:90` passwords, keys, recovery values and unlock material "never enter MCP arguments/results".
- `:138` "Human sessions keep their own idle/absolute settings; polling and API activity never prolong human login."
- `:152-153` human logout, expiry and sign-out end human and attended sessions; sign-out ends "every human and attended session of the profile; disclose independently enabled automation; API grants unaffected".
- `:203` "The human login receipt is the runtime-owned shared sign-in. ... Automatic resume defaults to interactive surfaces. That is a client-side default, not an authority control: agents authenticate with enrolled API keys or explicit attended delegation."

### 14. The sign-in's lifetime, retirement and login binding

Traced on 2026-10-10 after review, by static reading with nothing run, by a second reader who re-opened each locator.

- Nothing extends the stored sign-in after it is minted. The supplied-key resume door "does not advance either deadline" (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py:1167-1168`); the idle deadline is computed once at mint (`:959`) and tested at resume (`:1093`); a search of that file for extend, advance, slide and renew finds only the sign-in generation's advance (`:764`). The accepted sign-in record defers extension: "Until that decision is made, the receipt is not extended, and the session deadline governs" (`.vault/adr/2026-10-04-application-sign-in-adr.md:100`).
- A session admitted from the sign-in expires at the sooner of the sign-in's idle and absolute deadlines, fixed at admission (`src/cadrumo/application/user_profile/session_authority_admission.py:346`, `:371`); refresh refuses any session that is not a root key session (`:429`, `:453-454`). The receipt is minted once, at admission, and only when a password login asked for it (`src/cadrumo/entrypoints/runtime/session_owner.py:354-365`; `session_authority_admission.py:426`; `src/cadrumo/entrypoints/runtime/profile_connection_admission.py:141-145`).
- It follows that the session of every surface and the stored sign-in end at the same instant, the idle deadline counted from the password login, 15 minutes by default (`.vault/adr/2026-10-04-application-sign-in-adr.md:96`). After it a resume is refused and the receipt deleted (`acceleration_receipt.py:1294-1302`, `:1253-1270`), and only a password login creates another sign-in.
- The worker's slide of its in-process idle window writes one field of the in-process object (`src/cadrumo/adapters/persistence/storage/master_key/bucket_session.py:258-268`), on every secure-object access and with no check of who caused it (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:343-361`). It writes neither a lease nor the stored sign-in.
- The worker opens that in-process session with a five-minute idle window and an initial idle deadline equal to the lease's expiry (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:200-208`). A touch then sets the idle deadline to the sooner of five minutes from now and the absolute deadline (`bucket_session.py:258-268`), and an access after the idle deadline raises an expiry (`secure_objects.py:349-356`).
- The gate that refuses the password and the receipt login from the MCP frontend is a list of the command line and the terminal interface (`profile_connection_admission.py:136-140`); the adapter refuses a secret from any other frontend (`src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`) and so does the runtime (`src/cadrumo/entrypoints/runtime/profile_connection_operations.py:89-90`).
- On retirement the terminal interface discards its profile-bound view with the reason "expired" and exits to its outer loop (`src/cadrumo/entrypoints/tui/app.py:299-301`; `src/cadrumo/entrypoints/tui/runtime_session.py:155-157`, `:261-265`), which starts another attempt (`src/cadrumo/entrypoints/tui/installed_session.py:305-317`) whose host shows the login screen (`src/cadrumo/entrypoints/tui/runtime_admission.py:42-65`). Resume on that screen is an action the person presses (`src/cadrumo/entrypoints/tui/secret/runtime_login.py:157-168`, `:221-226`).
- On Windows a peer must first be the runtime's own account (`src/cadrumo/adapters/local_runtime/windows_login.py:93`). When the runtime's desktop can be witnessed, every such peer is bound to that desktop's logon, whatever started it (`:95-103`, `:112-120`). When capturing the witness is refused, which includes having no desktop, the peer's own token logon is used (`:104-111`). This file holds another session's uncommitted work and may change. Linux and macOS were not read.
- At resume the sign-in generation is checked first and the bound login second (`acceleration_receipt.py:1244-1249`, `:1303-1307`). A mismatch of either is refused and both halves of the stored sign-in are deleted (`:1253-1270`, `:1315-1332`) before the presented proof is unwrapped (`:1309`); only the key's length is tested earlier (`:1177`). The deletion can be partial. A presenter from another logon of the same account therefore ends the sign-in for every surface without holding a valid proof. The command-line frontend reaches this today.
- Operation access has the session and the request's frontend in one function (`src/cadrumo/application/user_profile/operation_access_policy.py:159-179`). The lock, sign-out and refresh handlers are dispatched from the connection, which carries the declared frontend (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:170-200`; `src/cadrumo/entrypoints/runtime/profile_host.py:95-104`), and sign-out checks the human kind through the authority (`profile_connection_sessions.py:202`).
- Starting an operation and delivering its secret require the owning session (`src/cadrumo/entrypoints/runtime/operation_host.py:315-317`, `:372-388`), and so does answering a review (`:517-532`). Cancel and detach are not bound that way.

## Not verified

- Whether the sign-in lease of a long-lived session is bound through the worker's five-minute in-process window of section 14. If it is, a session with more than five quiet minutes between storage accesses is refused before its lease ends.
- Whether the lock and sign-out handlers read the connection's frontend today, and the bodies of the receipt's deadline test and of the borrow door, which were not opened.
- What happens to sessions and operations after the worker is contained, and whether a deadline overrun on a section read or write raises inside `read_document`; the containment branch was read, not the framing code.
- Whether the command line has about 58 leaves that bind no runtime client at dispatch. The 24 declared exemption records were read; the count of such leaves and whether every one is exempt were not established.
- The code path by which an OS logout or OS lock retires a human session; the record states it (`:138`, `:159-160`), and evaluation reads a private-work flag (`src/cadrumo/application/user_profile/session_authority_policy.py:261-262`).
- That the stored sign-in can be unwrapped by any process of the account while live; the unwrap function was seen (`src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py:262`) but its callers and the keychain access rule were not.
- The frontend-keyed list was built from a search for comparisons against frontend literals and for `permitted_frontends` declarations. A gate written in another form, for example through a helper that receives the frontend as a parameter, could be missing.
- The desktop shell was read in its uncommitted state; the window files `native/desktop/frontend/src/shell/signIn.ts` and `native/desktop/frontend/src/App.tsx` are modified and the observer is untracked.
