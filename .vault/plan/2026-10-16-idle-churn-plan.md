---
tags:
  - '#plan'
  - '#idle-churn'
date: '2026-10-16'
tier: L1
related:
  - '[[2026-10-16-idle-churn-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:2396738366df0cc5f2e3184ad1dc43b1a4a34396cf8062babfb63aaf7afadd7e'
---

# `idle-churn` plan

Remove every idle polling loop, so a Cadrumo installation with the desktop open does no work while nothing changes.

## Description

Approved 2026-10-16. The operator asked in this session for the root causes of idle runtime CPU and process churn to be fixed, for every recurring check to use proper signals, and for the Python wait-with-timeout process loops to be migrated.

`2026-10-16-idle-churn-adr` governs every Step. Its evidence is `2026-10-16-idle-churn-audit`. S01 and S02 reduce per-turn cost with no new protocol. S03 adds the cues and the watch flag that S04-S07 consume. S08 and S09 replace the remaining timed waits in the transport and the runtime lifecycle. S10 re-measures the same idle desktop. S11 was added during execution: once cadrumo-agent `09bfc8b` relayed worker diagnostics on the agent's standard error, and CADRUMO-AGENT-SESSION1 had proved this on the rebuilt stage, the service's 0.2 s log-file tail became a duplicate path. S12 was added after the signed-in measurement in S10: each burst of input in the window started a `config activity` process (audit finding activity-report-spawn), although the window already holds the person session whose hold notes activity. It keeps the ADR's rule that the shell itself holds no runtime connection: the act goes through the long-lived `session hold` product child the window already runs.

S13-S15 were added on 2026-10-17. Signed-in idle measured 3.366% of one core, and the operator then ruled in this session that an app doing nothing must do no work. S13 stops the manager's heartbeat from running a worker custody pass on every ping. S14 and S15 remove the renderer's cursor-blink timer and the desktop log hub's 100 ms tick. Both run all the time because the TUI pane takes focus after sign-in and the log list is always mounted. The ping itself stays under `2026-10-04-runtime-manager-architecture-supervisor-contract-adr` until the operator rules on it. CADRUMO-BUILD-DEBUG owns the manager core, the desktop terminal, `app.rs` and `manager.rs`. CADRUMO-AGENT-SESSION1 owns cadrumo-agent.

S16-S19 were added on the same day under the same ruling. The operator asked for the TUI to be combed further, and five parallel combs plus a headless timer listing found what still woke it. S16 stops idle widgets animating. S17 replaces Textual's 100 ms Windows input loop. S18 moves the TUI's remaining interval checks to the deadlines and events they already know. S19 narrows the heartbeat's worker read to an activity count that revalidates no custody. The ping's 5 s cadence stays with `2026-10-04-runtime-manager-architecture-supervisor-contract-adr`. The plan-close review then reopened S15-S17: the screen host still ran a plain Textual app, and the append signal had no owner-only descriptor.

Concurrent owners: CADRUMO-FIX1 has uncommitted shared-person-hold hunks in `shell/sign_in/mod.rs`, `agent/mod.rs`, `agent/person.rs` and `shell/language.rs`. CADRUMO-RUNTIME-DEBUG or CADRUMO-BUILD-DEBUG has a `_report_failure` hunk in `session_hold.py`, and RUNTIME-DEBUG has hunks in `session_authority_core.py`. Edits keep those hunks, and commits stage only this plan's hunks. The operator's running desktop (pid 60364) is not restarted. CADRUMO-BUILD-DEBUG rebuilds `stage/Debug` when the operator closes it.

S20 was added on 2026-10-17 when the operator ruled on the ping, accepting the recommendation of 60 s while the runtime reports no work in flight and 5 s otherwise. It amends `2026-10-04-runtime-manager-architecture-supervisor-contract-adr` under that ruling. CADRUMO-BUILD-DEBUG handed `supervisor.rs` over for it and runs the manager's Rust tests, since Rust tests here run only through its managed targets.

## Steps

- [x] `S01` - Verify a service image once per connection and recheck only the kernel incarnation on later requests; `src/cadrumo_runtime/adapters/service_verification.py`.
- [x] `S02` - Wait for the earliest lease deadline or a custody change instead of the 0.1 s worker expiry loop; `src/cadrumo_runtime/host/worker_service.py`.
- [x] `S03` - Add sign-in, service-lease and attendance cues with coalesced publication and a sign-in watch flag, and publish language cues on operation completion; `src/cadrumo_client/contracts/session_events.py`.
- [x] `S04` - Drive the agent service from its connection events and stdin lifetime with cached generations; `src/cadrumo_agent_service/main.py`.
- [x] `S05` - Make the session hold block on one queue and emit unsolicited event lines; `src/cadrumo_runtime/host/session_hold.py`.
- [x] `S06` - Add the cadrumo-runtime session watch child; `src/cadrumo_runtime/host/session_watch.py`.
- [x] `S07` - Share one watch-driven sign-in observation across the sign-in view, language host and agent host, and push attendance changes to the window; `native/desktop/src-tauri/src/shell/sign_in/observation.rs`.
- [x] `S08` - Block idle transport loops on the channel and a wake handle; `src/cadrumo_client/transport/verified_transport.py`.
- [x] `S09` - Wake runtime lifecycle observation on deadlines, explicit wakes and Windows session notifications; `src/cadrumo_runtime/host/profile_connections.py`.
- [x] `S10` - Measure the rebuilt desktop at idle and record the result; `.vault/audit/2026-10-16-idle-churn-audit.md`.
- [x] `S11` - Drop the agent service's 0.2 s diagnostic file tail now that the agent relays worker diagnostics on its standard error; `src/cadrumo_agent_service/adapters/agent_diagnostics.py`.
- [x] `S12` - Note person activity through the held person session instead of a spawned config activity child; `native/desktop/src-tauri/src/shell/sign_in/mod.rs`.
- [x] `S13` - Answer a profile worker status request without waking its custody expiry pass; `src/cadrumo_runtime/host/worker_service.py`.
- [x] `S14` - Show a steady terminal cursor so a focused pane stops redrawing on a blink timer; `native/desktop/frontend/src/components/TerminalPane.tsx`.
- [x] `S15` - Wait for log records or file changes in the desktop log hub instead of a 100 ms tick; `native/desktop/src-tauri/src/logs/mod.rs`.
- [x] `S16` - Stop TUI widgets animating while idle: the status spinner only while progress shows, a steady text cursor in every Cadrumo Textual app, and onboarding progress without a ticking bar; `src/cadrumo/entrypoints/tui/components/status.py`.
- [x] `S17` - Wait in the TUI's Windows input loop for console input or stop, with a deadline only while an escape sequence is pending; `src/cadrumo/entrypoints/tui/windows_input.py`.
- [x] `S18` - Move the TUI's remaining interval checks to the deadlines and events they already know: the recovery-code handoff, the API-key status and the automation screen lifetimes; `src/cadrumo/entrypoints/tui/secret/registration.py`.
- [x] `S19` - Answer the supervisor heartbeat's in-flight count with a worker activity read that revalidates no custody; `src/cadrumo_runtime/host/session_owner.py`.
- [ ] `S20` - Ping a runtime that reports no work in flight every 60 s instead of every 5 s, moving its hang bound with the later ping; `native/manager/src/supervision/supervisor.rs`.

## Parallelization

S01, S02 and S08 are independent of the rest. S04, S05, S06 and S07 depend on S03, and S07 also depends on S05 and S06. S09 follows S08 because both change how the runtime's accept and connection loops wait. One session executes the Steps in order. Nothing is delegated.

## Verification

- Each Step's focused tests drive the real owner. A cue test performs the mutation and observes the cue on the connection. Expiry tests use the injected clock.
- Ruff, the format check, the import linter and the type runner pass on the touched files. For S07, cargo check, clippy and the crate's unit tests pass, along with the frontend type check.
- S10: with the rebuilt desktop open, signed in and idle for at least 60 s, the 30 s process enumeration shows no new Cadrumo child processes. Every long-lived Cadrumo process stays below 1% of one core. A `py-spy record` of the runtime and the worker shows no recurring work other than the supervisor's heartbeat, which since S20 an idle runtime answers once a minute.
- S20: the manager's clippy check and its `manager.rust` and `manager.supervision` tests pass through CADRUMO-BUILD-DEBUG's managed build, including the idle cadence, unknown count, late idle reply and idle hang cases.
- The plan closes after an integrated review of the changed behavior against the ADR.
