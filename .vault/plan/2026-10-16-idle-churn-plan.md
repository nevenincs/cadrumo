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
body_hash: 'sha256:d8f9fc0be674e0796702a3ff54e1c778e518c8072bfa4a4e7062c2a7485e76a1'
---

# `idle-churn` plan

Remove every idle polling loop, so a Cadrumo installation with the desktop open does no work while nothing changes.

## Description

Approved 2026-10-16. The operator asked in this session for the root causes of idle runtime CPU and process churn to be fixed, for every recurring check to use proper signals, and for the Python wait-with-timeout process loops to be migrated.

`2026-10-16-idle-churn-adr` governs every Step. Its evidence is `2026-10-16-idle-churn-audit`. S01 and S02 reduce per-turn cost with no new protocol. S03 adds the cues and the watch flag that S04-S07 consume. S08 and S09 replace the remaining timed waits in the transport and the runtime lifecycle. S10 re-measures the same idle desktop. S11 was added during execution: once cadrumo-agent `09bfc8b` relayed worker diagnostics on the agent's standard error, and CADRUMO-AGENT-SESSION1 had proved this on the rebuilt stage, the service's 0.2 s log-file tail became a duplicate path.

Concurrent owners: CADRUMO-FIX1 has uncommitted shared-person-hold hunks in `shell/sign_in/mod.rs`, `agent/mod.rs`, `agent/person.rs` and `shell/language.rs`. CADRUMO-RUNTIME-DEBUG or CADRUMO-BUILD-DEBUG has a `_report_failure` hunk in `session_hold.py`, and RUNTIME-DEBUG has hunks in `session_authority_core.py`. Edits keep those hunks, and commits stage only this plan's hunks. The operator's running desktop (pid 60364) is not restarted. CADRUMO-BUILD-DEBUG rebuilds `stage/Debug` when the operator closes it.

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

## Parallelization

S01, S02 and S08 are independent of the rest. S04, S05, S06 and S07 depend on S03, and S07 also depends on S05 and S06. S09 follows S08 because both change how the runtime's accept and connection loops wait. One session executes the Steps in order. Nothing is delegated.

## Verification

- Each Step's focused tests drive the real owner. A cue test performs the mutation and observes the cue on the connection. Expiry tests use the injected clock.
- Ruff, the format check, the import linter and the type runner pass on the touched files. For S07, cargo check, clippy and the crate's unit tests pass, along with the frontend type check.
- S10: with the rebuilt desktop open, signed in and idle for at least 60 s, the 30 s process enumeration shows no new Cadrumo child processes. Every long-lived Cadrumo process stays below 1% of one core. A `py-spy record` of the runtime and the worker shows no recurring work.
- The plan closes after an integrated review of the changed behavior against the ADR.
