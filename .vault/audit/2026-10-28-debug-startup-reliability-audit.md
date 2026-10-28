---
tags:
  - '#audit'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:49f37f85f9bf6fdcf835d40448a4a96b3c6d181d77762a280359c43263496ff3'
related:
  - "[[2026-10-28-debug-startup-reliability-plan]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-10-16-idle-churn-adr]]"
---

# `debug-startup-reliability` audit: debug warnings and first-launch agent reliability

## Scope

Review the user's 2026-10-28 running Debug build observations, current source changes for S01/S02 of 2026-10-28-debug-startup-reliability-plan, and independent Luna module/log summaries. Sol 6.1 high workers implement the fixes and Sol 6.1 medium independently reviews the integrated behavior. Preserve the parallel Claude session's edits and commits. Python log evidence comes from the active local Cadrumo log and native JSONL diagnostics, read with shared access and allowlisted fields only. Times below are UTC; the UI displays Europe/Madrid local time. Semantic discovery initially failed, then root started the installed service and searched current code and decisions successfully. Existing accepted provider-settings and idle-churn constraints govern unchanged exact-peer, custody and revocation behavior.

## Findings

### service-record-profile-stall | high | Native service verification held the shared profile guard for 49 seconds

At 12:33:41.759Z runtime PID64600 thread cadrumo-ipc_3 reported completed service_recheck_slow=48.881s. At 12:33:41.827Z the same thread reported profile_guard_slow hold=48.981s, wait=0, entered by ProfileConnectionExtensionRecordsMixin.extension_record. Original source diff confirms recheck_service ran inside host.guard for record input/access. Admission had the same ordering. The change moves native inspection outside the shared guard and revalidates exact current host, connection, service, session and lease under the guard before authority/access. The secret input/output and mutation disclosure fences remain. Relevant owners: `src/cadrumo_runtime/host/profile_connection_extension_records.py`, `src/cadrumo_runtime/host/profile_connection_services.py`, `src/cadrumo_runtime/adapters/service_verification.py:258`. A second completed recheck took39.394s at12:41:34.025Z without a matching guard warning. The slow native subcall itself is not attributed: three current probes of active service kernel identity, path resolution and stat each completed under1ms. Moving inspection removes profile-wide amplification, not the individual native stall.

### first-launch-timeout-budget | medium | Outer startup and admission could expire before a valid runtime exchange

Original desktop START_LIMIT was30s, while initial installed-client claim can use120s before main publishes service_ready. Native service admission used10s, and the Python frontend default matched10s. These mismatched bounds can terminate a healthy cold launch before the runtime exchange budget expires. The fix gives outer service startup180s for handshake, registration and cold interpreter headroom; native and Python service admission use the established120s exchange budget. Explicit short budgets and uncertain outcomes remain, with no admission replay. Owners: `native/desktop/src-tauri/src/agent/supervisor.rs:37`, `native/desktop/src-tauri/src/agent/person/native.rs`, `src/cadrumo_client/transport/frontend_client.py:512`. Retained live logs show successful service/gateway readiness and no retained native launcher failure, so the historical startup symptom is not conclusively attributed to this source defect. A rebuilt cold launch is separate acceptance.

### disconnect-admission-race | high | A retiring unleased recipient could be readmitted before registry removal

Disconnect retired authority, then performed fallible cleanup before removing connection maps. An unleased recipient remained visible in that interval and could receive new attendance. The fix marks its in-memory connection disconnecting under the same profile guard before authority retirement; authority facts, service admission and record access reject that lifetime even while cleanup retains the registry entry. No protocol or persisted schema changes. Owners: `src/cadrumo_runtime/host/profile_connection_sessions.py`, `src/cadrumo_runtime/host/profile_host.py`; deterministic coverage pauses cleanup and tests both direct attendance and pending admission. Independent source review found the marker/fence ordering sound.

### workbench-elapsed-warnings | low | Completed nested captures are latency evidence without an isolated performance cause

The one-second diagnostic_phase threshold emits calendar/capture/list WARNING records for successful work. calendar_schedule, census_observation, recheck, declaration_list_inputs, capture, read and read_and_store overlap; adding their durations double-counts. Census is read and then reread to reject a mixed snapshot. The callback reads stored census through operation journal and secure references. Declaration-list composition has no capture memory, so separate reads rebuild calendars; calendar computation builds a schedule, a filing-evidence calendar and an agenda. These are confirmed costs, not proof that consistency checks should be removed or unsafe memoization added. Worker request warnings start after request receipt and include dispatch plus reply; two-second threshold. Sources: `src/cadrumo/application/workbench_generation_calendar.py:401`, `src/cadrumo/application/workbench_generation_reader.py:387`, `src/cadrumo/application/workbench_generation_reader.py:504`, `src/cadrumo/application/workbench_generation_reader.py:700`, `src/cadrumo/application/modelo/declarations_list_operation.py:125`, `src/cadrumo_runtime/host/worker_operation_requests.py:75`. No latency speedup is claimed from this repair.

### sede-view-invalid-invariant | medium | The observed view request refused before browser execution but its exact invariant is not retained

At12:26:57.132-.153Z worker56092 refused ProfileWorkerSubmitRequest in0.022s, and runtime reported invalid OperationSubmit live.sede.view faults=INTERNAL_INVARIANT. The worker's registered-error refusal wrapper collapses the error into a fault code; no source frame/message in the retained logs identifies which invariant failed. Source route: `src/cadrumo_runtime/host/worker_operation_requests.py`, `src/cadrumo_runtime/host/operation_host.py:127`, `src/cadrumo_runtime/host/operation_host.py:1210`, `src/cadrumo/application/operations/registry.py:644`. Browser execution is not evidenced. No speculative payload, browser or custody change is made. Requires a safe reproducer or payload-free originating error identity before a cause-specific fix.

### provider-turn-invalid-request | medium | A separate ACP worker turn failed after service readiness

At12:49:34Z agent worker62520 reported ACP subprocess exit_code1, then streaming ingest classified the turn invalid_request. Multiple provider wire failures share that condition; the retained event does not identify which occurred. Service and gateway initialization records succeeded earlier. This is distinct from service startup and cannot currently be assigned to model selection, credentials or request construction. Provider credentials, conversation contents and raw payloads were not copied. No provider retry policy or model choice is changed.

### admission-pending-lifecycle-coverage | low | Longer native admission is not covered by a new pending-admission shutdown interleaving

Independent review found no authority breach: current runtime revocation prevents stale access, and admin/gateway publication waits for admitted service authority. The supervisor awaits admission inline, now bounded120s, so sign-in observation can wait for that exchange. Existing separate stop_running cleanup remains. A dedicated pending-admission shutdown/lock regression would strengthen coverage; the added native budget model and real child readiness tests cover delayed admission and bounded readiness, not every lifecycle interleaving.


### first-login-phase-deadlines | high | Normal first-login and readiness waits still use independent hard cutoffs

The user clarified that failure appeared during the first login, with a long login and unavailable agent profile capability, and explicitly ruled that GUI/multiservice flow must use signals and slots, with hard times only last-resort emergency termination. Further source tracing finds GUI native login120s versus CLI fallback30s depending on a status snapshot (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:269`, `native/desktop/src-tauri/src/process.rs`); worker startup45s with0.1s accept polling (`src/cadrumo_runtime/adapters/profile_worker.py:41`), proof45s (`worker_admission_budget.py`), another construction60s (`src/cadrumo_runtime/host/session_owner.py:247`), UI startup90s Promise.race (`native/desktop/frontend/src/shell/signIn.ts:141`), hosted agent ready60s (`src/cadrumo_agent_service/host/controller.py:186`). These independent limits can reject valid slow work. Native service admission also waits inline in the supervisor and occupies the shared person exchange slot while verification runs, delaying profile reads. Removing a timer alone can pin shutdown because service startup holds its lifecycle RLock while a ready-line Queue wait has no close/cancel wake. This requires correlated pending/terminal admission, responsive readiness/exit/cancellation signals and owner-bound emergency-only cutoffs, beyond S01's mismatch mitigation. These are confirmed source structures; the precise historical first-login failing seam remains unretained.

## Recommendations

Ship the verified S01/S02 fixes through the normal native build and exercise a cold launch before claiming the first-launch requirement is proven in the installed Debug package. Preserve exact native peer checks; if service_recheck_slow recurs, measure its kernel/path/channel subphases with payload-free diagnostics rather than weakening admission. Preserve workbench snapshot rechecks and attribute journal/calendar/census costs before changing caching. Reproduce the Sede invariant and provider invalid_request with safe error identity to select their fixes. No new costly decision is made by this audit.

## Verification

Independent integrated source review found no remaining critical/high defect after the disconnect marker. Python admission tests passed2, including11s simulated work and explicit short refusal without replay. Scoped Ruff, formatting, ty and rustfmt passed in worker runs. Runtime concurrency regressions and isolated CMake native tests are still being completed. One runtime test attempt failed during native fixture login before the regression body (DEADLINE_EXCEEDED at worker startup), so its result is an evidence gap rather than a passed regression or an attributed source failure. Root registry gate passed. Aggregate code/test checks and rebuilt live acceptance remain pending; this audit verdict is PENDING until applicable results are appended.

## Focused verification update

S02 committed as faa60b4d40; S01 committed as70c669358d. All8 new runtime concurrency cases now pass across focused runs. Final recipient_disconnecting rerun:1 passed,14 deselected,14.08s, exit0; log var/storage/development/.logs/test-runs/2026-10-28/20261028T132021.659987Z-pytest-10512-bea86780/run.log. This resolves the earlier missing full-assertion evidence after a stale collected test expectation and pre-body fixture startup failure. No production timeout was changed to make those runtime fixtures pass.

Isolated windows-tests-debug desktop-host-unit-test selected146 agent tests:146 passed,0 failed,559 filtered. Includes real child service-ready gates with startup clock aged131s and181s, plus native11s admission budget simulation. desktop-host-unit-clippy, desktop.fmt, Python admission2 tests, scoped Ruff/format/ty all passed. Native source files matched the tested CMake backend snapshot. Independent Sol medium review found no remaining critical/high source defect after the disconnect marker, with the pending-admission lifecycle test observation retained above. Root check-registry-gate passed. Full root code and change-scoped test gates are still running. The running user's Debug processes have not been replaced; no live cold-launch success is claimed.
