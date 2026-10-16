---
tags:
  - '#audit'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:6b7755278daaa24c00dba2294a461d8ef04fd1f26dd72dda330d7c0fc0609bcb'
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

## Recommendations

- For desktop-sign-in-polling, service-lease-polling, attendance-polling, language-hint-polling and session-hold-loop: replace each poll with a pushed invalidation cue and one re-read. This requires a decision on the cues and on how the shell observes sign-in without holding a runtime connection itself. See `2026-10-16-idle-churn-adr`.
- For service-image-rehash: verify the image once per connection and recheck the kernel incarnation on later requests.
- For runtime-lifecycle-poll and worker-expiry-loop: schedule work on deadlines and OS notifications instead of fixed intervals.
- For transport-idle-waits: block on the channel handle.
