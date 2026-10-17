---
tags:
  - '#audit'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:ca80d1a8ba7a85df46373dd856148a1390efcc1783a1b241dbf9f04061a0fbe0'
related: []
---

# `idle-churn` audit: `Idle CPU and process churn with the desktop open`

## Scope

The operator reported the local runtime using more than 2.5% CPU with the desktop open and idle. This audit measures the staged Debug package (`build/windows-x64/stage/Debug/app`) on 2026-10-16, 18:22-18:40, on a 24-logical-core Windows 11 host. The window was open, the profile signed in, and the TUI and two terminal panes were idle. Every Cadrumo process was sampled. Process creation was enumerated every 250 ms for 30 s. Per-thread CPU was diffed over 5 s windows. `py-spy record` sampled the runtime and its profile worker at 200 Hz for 20 s, and `py-spy dump` captured the other processes.

Measured over 30 s:
- The supervised runtime used 56% of one core, which is 2.3% of the machine.
- The profile worker used 12% of a core.
- The desktop host used 2.8%. The agent service, both session holds and the TUI were each below 0.4%.
- The desktop also started a new `cadrumo-runtime --format json config sign-in-status` process 12 times in those 30 s.

A single such read measured 1.3-1.7 s of CPU in the child, about 1.5 s of wall time, and 0.7-1.2 s of runtime CPU. The spawned children add roughly half a core that per-process sampling of long-lived processes does not show.

## Findings

### desktop-sign-in-polling | critical | Three independent 2-second desktop loops each observe sign-in by spawning a CLI process

The sign-in observer sleeps 2 s between reads (`native/desktop/src-tauri/src/shell/sign_in/observation.rs:81`). Each read runs a new `config sign-in-status` child (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:179-189`). The language host loops on its own 2 s timer (`native/desktop/src-tauri/src/shell/language.rs:228-231`), and each turn performs a status read, a `PROFILE_ID` read (the same leaf with identifiers revealed), a person exchange and a second status read (`language.rs:126`, `:152`, `:174`). The agent supervisor observes on its own 2 s `POLL` (`native/desktop/src-tauri/src/agent/supervisor.rs:36`, `:663`) through the same read (`native/desktop/src-tauri/src/agent/mod.rs:58`) and resolves the profile id with another child (`agent/mod.rs:68`). `Reads` shares only reads that overlap in time (`shell/sign_in/reads.rs:1`), so unaligned timers each pay for a child. The observed spawns came in runs of three about 1.7 s apart, separated by gaps of about 4.6 s. That matches the language cycle. Each child boots a full interpreter and the runtime then evaluates `sign_in_status` for it. This is the largest consumer, and it is the process churn the operator saw.

### service-lease-polling | critical | The agent service polls the runtime three times every 500 ms

`_serve` loops on `stop.wait(0.5)` and calls `client.claim()` on every turn (`src/cadrumo_agent_service/main.py:123`). `service.observe()` then calls `observe_generations`, which claims again and requests `extension_record_generation` (`src/cadrumo_agent_service/providers/persistence/store.py:96`, `:100`). With an agent running, `controller.published()` makes the same calls through `current_generations()` (`src/cadrumo_agent_service/host/controller.py:255`). The runtime services each claim with a full service verification and a session status (`src/cadrumo_runtime/host/profile_connection_services.py:54`, `:72`). It services each generation request with two verifications and three status evaluations (`src/cadrumo_runtime/host/profile_connection_extension_records.py:66`, `:69`, `:88`, `:93`, `:100`), and forwards it to the profile worker. In the runtime profile, 71% of samples were connection threads dispatching these requests.

### service-image-rehash | high | Every service request re-reads and re-hashes the 16 MB service image

`verify_service` reads the whole launch image through the confined reader and hashes it on every call (`src/cadrumo_runtime/adapters/service_verification.py:152`, `:155`). Image reading and hashing made up 33% of all runtime samples. Re-hashing the file on disk adds no evidence about the running peer. Its code was mapped from the bytes verified when the connection was admitted, and Windows refuses writes to a mapped image. The kernel incarnation check, which compares pid and creation time on the retained peer handle, is what binds later requests to that peer.

### session-facts-cost | high | Every session status rebuilds lock, enrollment, login and custody facts from disk and the OS

Each `_status` and each revalidation calls `facts()` (`src/cadrumo_runtime/application/session_authority_core.py:68`). That re-reads the profile lock state, the enrollment state through the Credential Manager and anchored custody files, the capsule password material, and the full OS login inventory (`src/cadrumo_runtime/host/profile_host.py:516-552`). One `facts()` call costs about 15-20 ms, and it is on the path of every polled request above.

### runtime-lifecycle-poll | high | The runtime accept loop revalidates every session twice a second whatever happens

The accept loop calls `profiles.poll()` before every `listener.accept(timeout=0.2)` (`src/cadrumo_runtime/adapters/server.py:217`, `:221`). The poll is throttled to once per 0.5 s (`src/cadrumo_runtime/host/profile_connections.py:432`). Each pass takes the OS login inventory, polls enrollments, and for each host checks binding replacement, approval expiry, lock-down and `revalidate_sessions()` (`profile_connections.py:452`). Revalidation was 75% of the pass. The main thread accounted for 23% of runtime samples, about 11% of a core, with nothing changing.

### worker-expiry-loop | high | The profile worker revalidates its custody binding from disk ten to twenty times a second

`_expire_custody` sleeps 0.1 s and then calls `custody.live_sessions()` and `human.expire()` (`src/cadrumo_runtime/host/worker_service.py:144-146`). Both reach `expire()`, which re-reads and verifies the automation profile binding files whenever a lease is held (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:191`). Lease expiry is a known deadline. This loop was 73% of the worker's active samples.

### language-hint-polling | medium | Language change notices are produced by re-reading a hint file per connection

`take_events` reads the bucket language hint from disk at most every 0.5 s for each connection holding a session (`src/cadrumo_runtime/host/profile_connections.py:175`, `:193`). It is called from each connection's serve loop on every idle turn. So the one pushed event in this path is itself driven by file polling.

### transport-idle-waits | medium | Runtime and clients wake every 1-50 ms per connection to peek pipes

The runtime's per-connection loop backs off from 1 ms to 50 ms between `read_ready` peeks (`src/cadrumo_runtime/adapters/server_connection_handling.py:213-219`). Every client's event reader wakes every 50 ms to take the exchange lock and peek (`src/cadrumo_client/transport/verified_transport.py:86`). Each wakeup is cheap. With about eight connections on both sides it still adds up to hundreds of wakeups per second and GIL handoffs.

### session-hold-loop | medium | Session holds wake four times a second and request status every 5 s

`session hold` waits on its input queue with a 0.25 s timeout and calls `client.status()` every 5 s, although retirement is already pushed (`src/cadrumo_runtime/host/session_hold.py:175-177`). The desktop also ran two holds for the same profile, one for the language host and one for the agent service. CADRUMO-FIX1 is consolidating them into one shared hold.

### attendance-polling | medium | The window polls attendance inventory every 2 s while signed in

`AttendanceRequests` re-reads the inventory on a 2 s timer (`native/desktop/frontend/src/components/AttendanceRequests.tsx:41`). Each read passes through the person bridge into a runtime `attendance_inventory` request.

### manager-supervision-poll | medium | The shared manager core wakes every 100 ms in whichever process supervises

The supervisor's wait is capped at `poll_interval`, 100 ms, even when it is only waiting for the next 5 s heartbeat (`native/manager/src/supervision/supervisor.rs:70`, `:992`). `desktop_host` also turns on a fixed 100 ms `POLL` (`native/manager/src/desktop_host.rs:29`). When no installed manager owns the runtime, the desktop hosts this core, so these wakeups land in the desktop process. The desktop adds its own 500 ms `supervision_continues` check (`native/desktop/src-tauri/src/app.rs:380`). The manager crate is shared and under another in-flight plan, so the idle-churn plan does not change it. The fix is to wait on the child's process handle, the command channel and the next heartbeat deadline.

### shutdown-watchdog-poll | low | The runtime's shutdown watchdog woke every 50 ms for the whole runtime lifetime

`RuntimeShutdownWatchdog._watch` looped on `stop.wait(0.05)` to notice an early finish (`src/cadrumo_runtime/host/shutdown.py:89`). It now blocks on the stop itself. It joins on exit only when the stop has been set.

### worker-authorization-accept | low | Each profile worker's authorization endpoint turned every 0.2 s

`WorkerAuthorizationServer._serve` accepted with `timeout=0.2` (`src/cadrumo_runtime/adapters/worker_authorization.py:137`), and the stage wait polled every 50 ms. Both now block on the endpoint or channel together with the server's stop.

### agent-diagnostic-tail | low | The agent service tailed hosted log files every 0.2 s

`AgentDiagnosticFiles._follow` re-scanned and re-read the hosted runtime log directory every 0.2 s while an agent ran (`src/cadrumo_agent_service/adapters/agent_diagnostics.py:306`). Since cadrumo-agent `09bfc8b`, the agent relays its worker's diagnostics on its own standard error, which the service already drains.

### lifecycle-sweep-reowe | high | Signed in, every lifecycle pass owed the next one, so passes ran each second forever

A pass observes the logins three times: once itself (`src/cadrumo_runtime/host/profile_connections.py:559`), once through each profile's lock-down check and once through each session's revalidation, both by way of the profile's facts. The saved sign-in sweep is rate-limited to once a second. A repeat observation inside that limit owed a pass at the limit's end even when it saw nothing new, so each pass owed another. Signed out no session is revalidated, so the loop never started there. Signed in, py-spy showed a pass every 0.92-1.08 s costing 80-150 ms, 9.9% of a core in the runtime with nobody at the machine. A rate-limited observation now owes a later sweep only when its logins, inventory completeness or hosted profiles differ from what the last sweep was given (`profile_connections.py:331-338`). `test_a_pass_whose_profile_checks_observe_the_logins_again_owes_no_further_pass` fails against the previous code.

### activity-report-spawn | medium | Each burst of person input in the window starts a `config activity` process

`usePersonActivity` reports keyboard, pointer, wheel and paste input at most once every 15 s (`native/desktop/frontend/src/shell/usePersonActivity.ts:4`). Each report runs a new `cadrumo-runtime --format json config activity` child (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:237`), which opens a CLI connection, resumes the sign-in receipt and notes activity. A child measured 0.5-1.2 s of CPU. While someone works in the window that is a process every 15 s. The window already holds a person session whose hold accepts an `activity` request (`src/cadrumo_runtime/host/session_hold.py:273`), and activity renews every human session of the same sign-in (`src/cadrumo_runtime/application/session_authority_activity.py:38`). The agent-access list likewise runs a `config profile automation list` child, but only when its settings panel opens. The window now sends each report as an `activity` request on the held person session (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:226`) and starts no process for it; the bridge accepts only that session's own status as the answer (`native/desktop/src-tauri/src/agent/person.rs:285`).

### agent-recovery-poll | medium | The agent gateway runs a direct-control recovery pass every 2 s

Signed in and idle, `cadrumo-agent` logged `Direct control recovery pass complete` every 2.0 s with nothing examined, and used 1.3% of a core at 89 context switches a second. The pass belongs to cadrumo-agent and is not changed here.

### remaining-platform-observation | low | Some observations stay periodic where no notification source exists or the work is not idle

- Without WTS session notifications the runtime observes logins every 0.5 s. That applies to POSIX hosts, a refused registration, non-desktop logons, and unknown lock states. The ADR records this allowance.
- The macOS worker guardian checks for parent loss every 0.2 s (`src/cadrumo_runtime/host/macos_worker_guardian.py:28`). kqueue `NOTE_EXIT` could replace it.
- Startup and in-flight operation waits remain bounded polls. These are the profile worker's startup accept, the supervised ready announcement and client operation settlement. They are not idle work.

## Recommendations

- For desktop-sign-in-polling, service-lease-polling, attendance-polling, language-hint-polling and session-hold-loop: replace each poll with a pushed invalidation cue and one re-read. This requires a decision on the cues and on how the shell observes sign-in without holding a runtime connection itself. See `2026-10-16-idle-churn-adr`.
- For service-image-rehash: verify the image once per connection and recheck the kernel incarnation on later requests.
- For runtime-lifecycle-poll and worker-expiry-loop: schedule work on deadlines and OS notifications instead of fixed intervals.
- For transport-idle-waits: block on the channel handle.

## Re-measurement after the fixes

Both stages were rebuilt at 22:07-22:18 from source that includes S03-S09 and S11, and their probes passed. Each desktop was then started from `build/windows-x64/stage/<configuration>/app` and left idle for 45 s. Every process whose image lies under that directory was sampled, along with all of its descendants (WebView2 and console hosts), for 120 s. Each process's CPU time was diffed. The process tree was enumerated every 0.5 s to catch spawned children.

Signed out, idle, as % of one core:

| Process | Debug (22:30) | Release (23:04) |
| --- | --- | --- |
| Supervised runtime | 0.000 | 0.013 |
| `session watch` child | 0.000 | 0.000 |
| Desktop host (`cadrumo.exe`) | 0.765 | 0.427 |
| WebView2 processes | about 0.74 | about 0.95 |
| Total | 1.505 | 1.384 |

No Cadrumo process was spawned in either window. The desktop's remaining wakeups, about 41 a second, are the manager core's 100 ms supervision wait and the 500 ms supervision check (see manager-supervision-poll). A WebView2 GPU process started at launch and exited inside the window. A further 90 s watch of the Release tree saw no new GPU process, so it does not recur.

The signed-in idle state, which the baseline above measured, needs the operator's sign-in. Each stage's desktop was then held open for 30 minutes waiting for that sign-in: Debug until 23:02, Release until 23:38. No sign-in came, so the signed-in re-measurement is still open. It is recorded below once measured.

On 2026-10-17 the Release stage, rebuilt with FIX1's package-identity manifests, was signed in at 04:43. The first 120 s window after a 60 s settle measured 38.4% of one core. It was not idle: 10 children were spawned, 7 of them `config activity` (see activity-report-spawn), so the operator was working in the window. A second window then waited until no input had reached the session for 125 s and spawned nothing. Signed in, idle, as % of one core:

| Process | Release (04:48) |
| --- | --- |
| Supervised runtime | 9.885 |
| WebView2 renderer | 2.273 |
| `cadrumo-agent` | 1.260 |
| WebView2 browser and GPU | 0.961 |
| Desktop host (`cadrumo.exe`) | 0.546 |
| Profile worker | 0.403 |
| Agent service | 0.169 |
| TUI, `session hold`, `session watch` | 0.013 |
| Total | 15.522 |

The runtime's share was lifecycle-sweep-reowe. Against the baseline, the profile worker dropped from 12% to 0.4% and no `sign-in-status` child was spawned. A re-measurement after the lifecycle fix needs a rebuilt stage.

Both stages were rebuilt with that fix (`67ccdb876c`) and Release passed both probes. The Release desktop was signed in at 05:32 and, after a 60 s settle, measured 05:33-05:35 with no child spawned and no input reaching the window. Signed in, idle, as % of one core:

| Process | Release (05:33) |
| --- | --- |
| `cadrumo-agent` | 1.238 |
| Desktop host (`cadrumo.exe`) | 0.709 |
| Supervised runtime | 0.477 |
| WebView2 renderer | 0.284 |
| Profile worker | 0.271 |
| Agent service | 0.206 |
| WebView2 browser and GPU | 0.103 |
| TUI | 0.077 |
| `session hold`, `session watch` | 0.000 |
| Total | 3.366 |

The baseline, signed in on the Debug stage, was 56% for the runtime, 12% for the worker, 2.8% for the desktop and about half a core more in 12 spawned children per 30 s. What remains is agent-recovery-poll in `cadrumo-agent`, manager-supervision-poll in the desktop host, and the runtime's 23 context switches a second, which were not traced further. The Debug stage was not measured signed in: its backend probe fails under the package-identity registration another plan owns, and the operator's Task Manager check uses it.

## Plan-close review

The integrated review of S01-S12 (`286f2033e4` to `a557048915`) required revision for one high finding. The review and the fixes below judged committed code; other sessions' uncommitted edits were read only for context.

### activity-refusal-ends-the-person-hold | high | Any refused activity report ended the `session hold`, and with it the window's person session

S12 sent activity to the hold, whose generic handler answered any refusal from `note_activity`, including the transient `OS_SESSION_UNAVAILABLE`, with `session_refused` and exited. Separately, the desktop bridge dropped its stdin after every refused reply, so even a hold that survived a refusal, as `5a628ad0f5` made the service admission do, exited on end of input. A burst of typing while the login could not be observed would end the session the agent's lease hangs from. The hold now refuses only that report as `unavailable` and keeps holding on `OS_SESSION_UNAVAILABLE`, and ends on any other denial (`src/cadrumo_runtime/host/session_hold.py:274`). The bridge keeps its stdin after a refusal correlated with the request it sent (`native/desktop/src-tauri/src/agent/person.rs:243`, `:279`); a hold that ended is then seen closed. `test_an_uncertain_os_observation_refuses_only_that_report_and_keeps_the_hold` fails against the previous hold, and `a_refusal_of_this_request_keeps_the_bridge_and_the_next_request_is_answered` covers the bridge.

### parked-accept-reports-no-tick-age | medium | A parked accept loop reported no tick age even past the deadline it was given

The heartbeat's only liveness signal read zero for the whole park. The loop now records when its wait was due to end, and the age counts from that instant, so a wait that outlives its own deadline shows; a park with no deadline still reads zero (`src/cadrumo_runtime/adapters/server.py:98`, `:245`). `test_a_park_that_outlives_its_deadline_reports_the_overrun_as_tick_age` fails against the previous code.

### sign-in-sweep-state-outside-the-guard | medium | The sweep's rate-limit state was read and written outside the guard

Request threads observe the logins too, so two observations could both sweep, or record each other's swept inputs and lose a deferred sweep. One observation now decides under the guard and claims the sweep before running it (`src/cadrumo_runtime/host/profile_connections.py:333`). `test_two_observations_at_once_run_one_sign_in_sweep` fails against the previous code.

### wts-callback-takes-the-connections-guard | medium | The session-change window procedure waited on the runtime's guard

`os_session_changed` runs in the window procedure Windows calls, and took a guard that `prepare_registry` holds across building the operation registry. It now sets an event of its own and the native wake, and the pass consumes the event (`profile_connections.py:527`). `test_a_reported_session_change_never_waits_on_the_runtime_guard` fails against the previous code.

### lock-state-push-assumed-for-every-logon | medium | A registered session notification is taken as covering every logon the runtime answers for

The 0.5 s observation stays only while notifications are not registered or a logon reports no lock state. Registration with `NOTIFY_FOR_ALL_SESSIONS` (`src/cadrumo_runtime/adapters/windows_session_notifications.py:81`) is assumed to deliver lock, unlock, logon and logoff for every answered logon, including a runtime outside the locking session, the Session 0 shape the lifecycle policy requires it to admit. Delivery is only exercised with a posted message. Recommendation: decide whether a logon outside the registering session keeps a long fallback interval, and verify real delivery on a disposable host.

### tui-status-and-lifetime-timers-remain | low | Three TUI screens keep fixed-interval loops while they are open

The restricted API-key session app (`src/cadrumo_runtime/host/frontend/tui/runtime_session.py:50`, `:164`) reads `client.status()` every 10 s although retirement is pushed and subscribed, and the automation inventory and decision screens (`profile/automation_inventory.py:129`, `secret/automation_decision.py:100`) run 0.5 s timers against known deadlines. None of them runs in a person's signed-in desktop at rest, which shows the human workbench. Each status read is a runtime request, and so a lifecycle pass. Recommendation: decide whether they join this ADR's scope as a follow-on Step.

### service-generations-stale-across-two-service-connections | low | A cached extension-record generation is invalidated only by its own service

`src/cadrumo_agent_service/providers/persistence/store.py:103-124` keeps a generation until its own write or a pushed frame. One service per profile is consistent; two would not see each other's writes. The ADR's Consequences accept this class. Recommendation: decide whether a records-generation cue is needed or one service per profile is an invariant to assert.

### bootstrap-reset-replay-timing | medium | `test_bootstrap_reset[reset-and-replay]` failed once in nine runs under load

The failing run logged `profile_worker_control_dispatch_slow` three times, and the test's check that a refused replay leaves the sign-in generation unchanged (`src/cadrumo_runtime/host/tests/test_bootstrap_reset.py:184`) failed. After a password reset, the lifecycle pass retires the replaced binding and revokes the sign-in against the successor custody (`src/cadrumo_runtime/host/profile_host.py:700-702`). Since S09 that pass is owed one interval after the reset request, so a replay round trip slower than 0.5 s can see it land between the test's capture and its check. Waiting for the host's retirement before the capture does not fit the test's model: the generation observed under the original binding then no longer reads as advanced. Recommendation: the test's owner decides the intended sequencing of reset, retirement and replay.

Pending verification, not code defects: the POSIX `wait_readable` and accept paths have no integration test; real WTS delivery, RDP and Session 0 are untested; `test_lifecycle_wake.py` fakes the profile host, so no test ties `lifecycle_due()` to every deadline a pass acts on (binding replacement has none and relies on request-driven passes); and the `CancelIo` and handle-close race in `src/cadrumo_client/transport/windows_channel.py:227-245` when a peer closes during a wake.
