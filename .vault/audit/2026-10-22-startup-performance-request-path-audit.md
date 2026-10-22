---
tags:
  - '#audit'
  - '#startup-performance'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:18e5323fdf116729bd3becfcf82ea1cca29b9fc325e07768155eed9c863e3863'
related: []
---

# `startup-performance` audit: `Sign-in to first screen request-path audit`

## Scope

The operator reported on 2026-10-22 that the desktop takes 40-50 s from launch to a usable profile, against an expectation under 2 s, and that startup logs a run of `session_hold_request_slow` warnings: "no warning allowed. fix the roots causes. if you have to refactor everything". Evidence is the operator's 13:26 run of `build/windows-x64/stage/Release/app` (`%LOCALAPPDATA%/cadrumo/logs/cadrumo-native.jsonl` host 16132 and `cadrumo.log` 11:26-11:33Z), plus a reproduction on a disposable storage root against an independent copy of the same stage: a synthetic profile, the packaged runtime with `--configured-root`, the packaged CLI login and a desktop-style `session hold --password-stdin`, every process sampled with `py-spy record` at 250 Hz. Timings are wall clock on the operator's host under its usual concurrent load; the reproduction profile is empty, so its operation times are a lower bound for a real profile.

### Measured sequence, operator run

| Stage | Interval |
| --- | --- |
| Desktop start to runtime ready | 4.4 s (runtime `main_import` 1.8 s) |
| Manager ready | 6.0 s |
| `config profile list` helper before the sign-in form | 3.3 s |
| Password submitted to `config login` helper exit | 5.9 s |
| Agent "prepare" (status child and waiting on the shared person hold) | 13.5 s |
| First `language_observe` on the hold (first worker operation) | 10.3 s, of which submit 7.1 s |
| TUI first screen: preferences, five overview pages, status, workbench generation | about 20 s, each operation 0.6-2.1 s |

### Reproduction, empty profile

| Step | Time |
| --- | --- |
| `config profile list` | 1.3-1.6 s |
| `config login` | 5.2-5.6 s |
| `sign-in-status` | 1.5 s |
| `session hold` admitted | 2.1-2.5 s |
| One `user-profile.view` page through the hold | 0.83 s median |
| A bare runtime round trip (`status`) | 0.05 s median |
| `config profile status` | 3.6-3.9 s |

## Findings

### authority-facts-per-round-trip | critical | Every runtime round trip rebuilds authority facts from disk and the OS, several times

`RuntimeProfileHost.facts` (`src/cadrumo_runtime/host/profile_host.py:535`) re-reads the profile lock (`automation_profile_lock.py:63`, which takes the custody root lock, re-prepares directories, re-validates the password capsule binding and reads two records), the enrollment state (`automation_enrollment_custody.py:36`, the same lock plus the control witness and Credential Manager read), and the full LSA logon inventory (`src/cadrumo_runtime/host/profile_connections.py:314`, `src/cadrumo_runtime/adapters/windows_login.py:192`, which enumerates every logon session on the host and reads each twice). Measured on a warm idle dev tree: lock state 6.7 ms, enrollment state 7.8 ms, binding 1.6 ms, logon inventory 23 ms. A single request calls it more than once: a login four times, an operation reply twice (authorize and contract status). One operation is five to eight round trips (contract, submit, start, observe, result), and the worker's own authorization callbacks add more. `facts` was 30% of all runtime samples. The idle-churn decision kept "the authority checks on every read unchanged"; their cost, not their existence, is the defect.

### worker-binding-per-guard | critical | The worker re-validates the password capsule up to three times per guard and five guards per operation

`guard_binding` (`src/cadrumo_runtime/host/operation_authority.py`) resolves the binding off-loop through `ProfileWorkerCustody.require`, enters `section` (another `require`) and leaves it through `expire` (`src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:128-200`). Each calls `validate_automation_profile_binding`, which loads the committed capsule through anchored directory opens (`custody/capsule.py`, `filesystem_primitives.py`). Admission, submission release, operation release, observation release and projection release each guard, so an operation re-reads the capsule about fifteen times. `guard_binding` was 22% of the worker's event-loop samples.

### redaction-opens-tax-authority | high | The log scrubber opens the 118 MB tax authority in every process

Almost every log line carries a token the NIF-IVA scan sends to the gate (`TASK1`, `LOCK`, `HTTP`). `RegistryTaxIdentityAdmission.admits_nif_iva` (`src/cadrumo/domain/calculations/registry/tax_identity_admission.py:76`) then admits the bundled authority, which SHA-256 hashes the whole 118 MB SQLite file (`authority_store.py:197`), decodes the snapshot globals and resolves the catalogue; each later call re-resolves it. It cost 0.75 s of the login helper (30% of its samples, the 0.5 s gap before every client's `existing_connect`) and 19% of the worker's samples.

### worker-cold-first-operation | high | The first operation after sign-in waits for worker imports and registry composition

The worker is spawned at sign-in (`cadrumo_runtime.host.worker`), imports for 2.8 s of samples on the empty profile, composes operation dependencies on first use (`operation_host._compose`, `compose_operation_dependencies`, 1.2 s) and then serves. On the operator's host the first `user-profile.view` submit took 7.1 s.

### sign-in-process-chain | high | Sign-in is a chain of separately started Python processes, each re-admitting

Before the form the desktop runs `config profile list` (3.3 s). The password goes to a `config login` child (5.9 s) that persists a receipt; the desktop then starts `session hold` (receipt resume, 2.1-2.5 s), the TUI (its own receipt admission) and the agent's status child and person hold. Each child pays interpreter start, its imports and the redaction cost above before its first request. `session watch` is already a long-lived child per window.

### tui-first-screen-serial-operations | high | The first screen is a dozen serial operations

The TUI reads preferences, then the overview in five pages (the 20,000-byte page bound, `view_operation.py`), status and the workbench generation, one after another. At 0.6-2.1 s per operation this is about 20 s before Home.

### authority-full-hash-per-process | medium | Every process that opens the authority hashes all 118 MB

`SQLiteAuthorityReader.__init__` computes the database digest (`authority_store.py:197`) in every process: login helper, status helper, worker, TUI. Warm it costs 0.12-0.19 s; cold, it reads 118 MB from a slow disk.

### lock-debug-volume | low | Custody and journal locks log two DEBUG lines per acquisition

The operation journal lock alone wrote 1,548 lines in seven minutes (`src/cadrumo/core/locks.py`), each scrubbed by the redaction funnel above.

### slow-request-warning | info | The `session_hold_request_slow` warnings are symptoms

`src/cadrumo_runtime/host/session_hold.py:383` warns at 1 s. Every warning in the operator's run is explained by the findings above; the threshold is correct and stays.

## Recommendations

- authority-facts-per-round-trip and worker-binding-per-guard: a decision is needed on serving the re-check from an observation that the OS invalidates (directory change notifications on the custody folders, WTS session notifications) instead of re-reading per call.
- sign-in-process-chain: a decision is needed on removing CLI children from the sign-in path, which amends the desktop shell's sign-in observation.
- worker-cold-first-operation: a decision is needed on a pre-started unbound worker, as the KDF child already is.
- redaction-opens-tax-authority, authority-full-hash-per-process, lock-debug-volume, tui-first-screen-serial-operations: implementation within existing decisions.

### progress-request-path | info | S01-S04 measured on the same package copy

The disposable-root harness ran against one independent copy of the operator's stage, first as staged and then with only the S01-S04 modules overlaid and compiled by the package's own interpreter; every overlaid module matched its pre-change source in the copy. Empty profile, operator's host, same session.

| Step | Before | After |
| --- | --- | --- |
| One `user-profile.view` page through the hold (median of 8) | 0.828 s | 0.153 s |
| Runtime `status` round trip (median) | 0.052 s | 0.007 s |
| Hold `activity` (median) | 0.103 s | 0.010 s |
| Hold `attendance_inventory` (median) | 0.048 s | 0.001 s |
| First `language_observe` after sign-in | 2.470 s | 1.869 s |
| `config profile status` | 3.6-3.9 s | 2.6-2.7 s |
| `config login` | 5.6 s | 5.2 s |
| `session hold` admitted | 2.1 s | 2.0 s |

Per-operation cost fell about fivefold. Process start, imports and the worker's cold first operation, which dominate sign-in, are unchanged by these Steps.

### progress-tui-first-screen | info | S09 cut the operations and imports before Home

The operator's runtime log for a TUI start before these Steps shows the preferences page at 1.6 s and five overview pages at 1.1-2.0 s each before the first screen (`tui_initial_screen_ready` 7.2-8.6 s for an incomplete profile). A complete profile then also read the workbench generation and a status page, and every Home refresh read the five overview pages again.

| Before Home | Before S09 | After S09 |
| --- | --- | --- |
| Profile view operations | preferences, 5 overview pages, status page | preferences, 2 status pages |
| Workbench graph import (2.6 s in development) | after the first profile read, serially | beside the preferences read |
| Profile view operations per Home refresh | 5 overview pages | 1 status page |

The profile pane's overview is read off the capture whenever a status names a newer revision; opening the pane during that read waits for it. Only an incomplete profile, which opens on the profile pane, reads the overview before its first screen. The launch time on the rebuilt stage is S10's measurement.

The runtime TUI suite also exposed an intermittent restricted-session test: its request button sat below the fold once the asynchronous status rows filled, so the pilot's click missed in 2 of 3 runs. The test now scrolls the button into view, as its login branch already did; 6 of 6 runs pass.

### generation-in-process-measurement | info | Where one workbench generation's time goes

Measured in the native workbench test (real runtime in-process, real profile worker) with storage on the operator's C: drive; no sampling profiler. A first run under py-spy with child processes leaked handles and was stopped by the host's security tripwire; the figures here come from in-process instruments only: a client and runtime frame timeline, an audit hook counting opens, and cProfile around the worker's capture.

| Segment of one 1.86-2.0 s generation | Time |
| --- | --- |
| Contract, submit and start | about 145 ms (contract alone 38 ms) |
| Worker capture (permit to release) | about 960 ms |
| Settlement until the operation advances | 80-550 ms, median about 120 ms |
| Last observation and five result pages | about 250 ms; each page is a worker request plus one authorize cycle, about 25 ms |
| Client restore and verification | about 200 ms |

Per generation: about 70 frames each way (250 KiB), 12.7 worker authorize/release/acknowledge cycles answered in about 0.4 ms each, about 128 opens in the runtime process. Inside the worker capture: the workspace field manifest walked 3 times (77 ms each), about 1,700 `stat` calls (210 from the log handler's per-record descriptor check, 400 from `profile_worker_binding.require_session`), about 110 DEBUG records at about 3.9 ms each through the file handler, 11 profile record loads.

The Y: drive stalls under concurrent sessions (hardened write p90 0.5 s, one 23.8 s); C: is a steady 3.5 ms, so journal and settlement figures from tests on Y: overstate the operator's cost.

S13 caches the manifest walk per traversal-root set: about 230 ms less per generation after a worker's first. The log handler and lock records belong to another workstream's files and were handed to it with these figures; the `require_session` stat is a storage-replacement check left unchanged.
