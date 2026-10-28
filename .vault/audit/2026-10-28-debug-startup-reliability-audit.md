---
tags:
  - '#audit'
  - '#debug-startup-reliability'
date: '2026-10-28'
modified: '2026-10-28'
body_schema: 'body-v2'
body_hash: 'sha256:9aaf6e01b90da997bb2b85f69d5fb025587f29a11979945c18a2132565ee07b2'
related:
  - "[[2026-10-28-debug-startup-reliability-plan]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-10-16-idle-churn-adr]]"
---

# `debug-startup-reliability` audit: debug warnings and first-launch agent reliability

## Scope

Review the user's2026-10-28 running Debug observations and S01–S12 of2026-10-28-debug-startup-reliability-plan. Luna6 supplies bounded module/log summaries; Sol6.1 medium/high implements and independently reviews the fixes. Preserve the parallel Claude session's edits and commits. Live logs were read with shared access and allowlisted fields only. Times are UTC; the UI displays Europe/Madrid local time. Accepted provider-settings, idle-churn and signal-driven startup decisions govern peer identity, custody, cancellation and revocation.

## Findings

### service-record-profile-stall | high | Native service verification held the shared profile guard for 49 seconds

At 12:33:41.759Z runtime PID64600 thread cadrumo-ipc_3 reported completed service_recheck_slow=48.881s. At 12:33:41.827Z the same thread reported profile_guard_slow hold=48.981s, wait=0, entered by ProfileConnectionExtensionRecordsMixin.extension_record. Original source diff confirms recheck_service ran inside host.guard for record input/access. Admission had the same ordering. The change moves native inspection outside the shared guard and revalidates exact current host, connection, service, session and lease under the guard before authority/access. The secret input/output and mutation disclosure fences remain. Relevant owners: `src/cadrumo_runtime/host/profile_connection_extension_records.py`, `src/cadrumo_runtime/host/profile_connection_services.py`, `src/cadrumo_runtime/adapters/service_verification.py:258`. A second completed recheck took39.394s at12:41:34.025Z without a matching guard warning. The slow native subcall itself is not attributed: three current probes of active service kernel identity, path resolution and stat each completed under1ms. Moving inspection removes profile-wide amplification, not the individual native stall.

### first-launch-timeout-budget | medium | Outer startup and admission could expire before a valid runtime exchange

Original desktop startup used30s while initial claim could use120s; native and Python service admission used10s. These mismatches could terminate valid cold startup. S01 first aligned those budgets as mitigation. The final implementation supersedes that mitigation with signal-driven pending admission and one centralized owner timeout. Owners include native/desktop/src-tauri/src/agent/supervisor.rs, native/desktop/src-tauri/src/agent/person/native.rs and src/cadrumo_client/transport/frontend_client.py. Retained live logs show service/gateway readiness, so the precise historical failing seam is not conclusively attributed. Rebuilt cold launch remains separate acceptance.

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

### first-login-phase-deadlines | high | Normal first-login and readiness waits still use independent hard timeouts

The user clarified that failure appeared during the first login, with a long login and unavailable agent profile capability, and explicitly ruled that GUI/multiservice flow must use signals and slots, with hard times only last-resort timeout termination. Further source tracing finds GUI native login120s versus CLI fallback30s depending on a status snapshot (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:269`, `native/desktop/src-tauri/src/process.rs`); worker startup45s with0.1s accept polling (`src/cadrumo_runtime/adapters/profile_worker.py:41`), proof45s (`worker_admission_budget.py`), another construction60s (`src/cadrumo_runtime/host/session_owner.py:247`), UI startup90s Promise.race (`native/desktop/frontend/src/shell/signIn.ts:141`), hosted agent ready60s (`src/cadrumo_agent_service/host/controller.py:186`). These independent limits can reject valid slow work. Native service admission also waits inline in the supervisor and occupies the shared person exchange slot while verification runs, delaying profile reads. Removing a timer alone can pin shutdown because service startup holds its lifecycle RLock while a ready-line Queue wait has no close/cancel wake. This requires correlated pending/terminal admission, responsive readiness/exit/cancellation signals and owner-bound shared timeout, beyond S01's mismatch mitigation. These are confirmed source structures; the precise historical first-login failing seam remains unretained.

## Recommendations

Complete the signal-driven first-login and service orchestration governed by2026-10-28-debug-startup-reliability-adr, then exercise a rebuilt cold launch before claiming the installed Debug requirement is proven. Preserve exact native peer checks; if service_recheck_slow recurs, measure its kernel/path/channel subphases with payload-free diagnostics rather than weakening admission. Preserve workbench snapshot rechecks and attribute journal/calendar/census costs before changing caching. Reproduce the Sede invariant and provider invalid_request with safe error identity to select their fixes.

## Signal-driven implementation and review update

The source now uses correlated pending human login and service admission with terminal cues, exact-attempt claim/cancel, dispatcher readiness and generation-bound native completion. Waiting releases shared request slots. The earlier admission-pending-lifecycle observation is superseded by this implementation and its cancellation/profile-change interleavings. Runtime and client wire version4 rejects the previous cohort rather than silently mixing incompatible contracts.

Timeout is the sole programming term for the last-resort bound. TimeoutPolicy and TimeoutDeadline carry one absolute owner budget across dependent phases and cleanup. Names, protocol refusals, native projections and localized UI messages were migrated together. Existing behavioral tests were updated; no terminology-enforcement tests were introduced. Historical ledger entries remain append-only.

Independent review exposed cancellation that fenced publication but left KDF waits or queued secrets alive. The repair adds an exact-proof cancellation channel separate from busy proof traffic, cancellable local capacity and same-domain OS lock waits, exact-child containment/reaping and reader cleanup. Windows legacy-lock and Linux helper cancellation tests passed. The parent admission queue and shared worker-construction join now observe the same token and owner deadline, releasing a cancelled login's secret and slot without cancelling another proof or the shared constructor. The final independent Sol6.1 high delta review passed after20 construction tests and3 cancellation-token tests. Crypto/token coverage passed51 tests with2 platform skips; native macOS execution remains unverified.

Agent preflight, catalogue and retirement review found two additional issues: unconfirmed catalogue/probe child cleanup lost its owner, and replacement retirement renewed its budget. Corrections retain unsettled child scopes and forward the existing deadline. Credential claim, generation and record reads now consume that deadline, and cancellation closes the exact transport without waiting for its held exchange lock. Public async HTTP transport wakes on cancellation with bounded response size and no independent phase timeout. Independent S09 review passed; real Windows held-reply cancellation, HTTP completion/cancellation, cleanup ownership and deadline-graph tests passed. Unknown containment retains ownership and uses a generic failure rather than claiming the agent was stopped.

Native functional checks passed150 agent,56 sign-in/helper,33 manager,26 runtime-client and77 platform cases, plus manager supervision and scoped fmt/clippy. Independent integration review then found a high opening-ownership gap: watch/direct sign-in/resume could wait for hello before registering a connection for close, retaining shutdown and a password until timeout. A medium exchange-queue race could lose a close notification between predicate check and condition wait. Both findings are now corrected and independently reviewed. Opening cancellation is retained before connect/hello, stop signals precede dependent joins, passwords are wiped and publication is fenced. Queue close uses the condition mutex. The final evidence below supersedes the earlier intermediate native counts. The running Debug processes have not been replaced.

## Module and function map

Luna6 supplied the bounded read-only module summary; Sol6.1 implementation and review evidence determines the conclusions above.

| Component | Owning source and behavior |
| --- | --- |
| Timeout policy | `src/cadrumo_client/contracts/deadline_budget.py` defines TimeoutPolicy and absolute TimeoutDeadline; dependent startup phases use remaining time rather than resetting it. |
| Pending admission | `profile_connection_login.py` and `profile_connection_services.py` begin bounded exact attempts, publish completion cues, claim/cancel terminal results and fence late publication. Typed contracts live in `profile_access.py`, `service_access.py` and `session_events.py`. |
| Worker readiness and proof | `session_owner.py` joins one construction and serializes proof; `worker_service.py` publishes readiness after authenticated dispatchers exist. `worker_proof_control.py` carries exact-attempt cancellation independently of proof traffic. |
| Custody cancellation | `proof_cancellation.py` synchronizes callbacks and unsubscription. `kdf_supervision.py`, `_kdf_file_lease.py` and `_kdf_cancellation.py` wake capacity, OS-lock and exact-child waits and preserve lease ownership through containment and reader cleanup. |
| Agent startup | `service.py`, `host/controller.py` and `host/store_lifecycle.py` carry one owner through preflight, credential resolution, readiness and retirement. Provider catalogue/auth sources retain unresolved invocation scopes and deny replacement work. |
| Credential IPC | `providers/application/agent_credentials.py` passes the owner through the store graph. `service_client.py` clamps supplied and initial owner deadlines; `verified_transport.py` validates exact replies and closes pending I/O without waiting for the exchange it must wake. |

## Shared-tree verification and business-date compatibility

During implementation, a separate working-tree rename changed persisted `payment_cutoff_on` and related filing-date/export spellings to timeout names. Published Modelo100/2025 authority then failed strict decoding before a capability test could reach its handler. Canonical schema/caller spellings and the `casilla_triple_cutoff` predicate value were restored without an authority migration or compatibility alias. Direct authority decoding and the previously failed capability case now pass; the family has68 passing cases across focused runs. These business dates are distinct from orchestration timeouts.

The broad code gate completed with7 of14 failing checks while the shared source was changing. Its findings included coedited Modelo imports/syntax/types, transient source-read failure, and an invalid generated import inventory. The inventory was regenerated. Fresh configured typing still reports coedited Modelo findings; three startup-test typing diagnostics were repaired and their3 behavior cases and three-platform typing pass. Fresh frontend check passes23 tests plus types/lint/format. The broad Python test gate is still running from its earlier loaded snapshot; its result must be reported separately from fresh scoped corrections.

## Verification

The focused updates preserve intermediate results and failures. Final verification below supplies the current scoped verdict and distinguishes repository-wide gate failures from installed live acceptance.

## Focused verification update

S02 committed as faa60b4d40; S01 committed as70c669358d. All8 new runtime concurrency cases now pass across focused runs. Final recipient_disconnecting rerun:1 passed,14 deselected,14.08s, exit0; log var/storage/development/.logs/test-runs/2026-10-28/20261028T132021.659987Z-pytest-10512-bea86780/run.log. This resolves the earlier missing full-assertion evidence after a stale collected test expectation and pre-body fixture startup failure. No production timeout was changed to make those runtime fixtures pass.

Isolated windows-tests-debug desktop-host-unit-test selected146 agent tests:146 passed,0 failed,559 filtered. Includes real child service-ready gates with startup clock aged131s and181s, plus native11s admission budget simulation. desktop-host-unit-clippy, desktop.fmt, Python admission2 tests, scoped Ruff/format/ty all passed. Native source files matched the tested CMake backend snapshot. Independent Sol medium review found no remaining critical/high source defect after the disconnect marker, with the pending-admission lifecycle test observation retained above. Root check-registry-gate passed. Full root code and change-scoped test gates are still running. The running user's Debug processes have not been replaced; no live cold-launch success is claimed.

## Final verification

Scoped startup repairs: VERIFIED, with independent S09, S12 and integrated native delta reviews passing. Final native evidence is150 agent cases,59 sign-in/helper cases,33 GUI-manager cases,27 runtime-client cases and79 platform cases, plus manager supervision and scoped fmt/clippy. The Windows busy-pipe test holds availability beyond a1ms server default and then connects successfully; cancellation before and during kernel wait also passes. Kernel waiting consumes the original owner's remaining timeout. All3 stalled-hello/window-close regressions pass. A prior full sign-in run hit one unchanged10-second helper guard; isolated and complete59-case reruns pass on identical source and guards. That one-off guard failure's exact cause is unretained.

Fresh Python acceptance passes restored-profile native TUI handoff, enrollment across lock/password resume, guarded recovery with persisted mutation and both negative-login cases. Negative login returns the expected passphrase refusal with exit2. Capability coverage is68 passing cases across corrected runs; actual certificate-write subprocess also passes. The fixture repairs consume worker readiness, preserve its configured context, avoid joining an intentionally persistent presentation worker, and provide canonically eligible fiscal facts. Canonical operator-revocation imports were repaired. Windows/Linux/macOS scoped typing, Ruff and formatting pass for these repairs. The Python startup cohort has73 files passing Ruff and formatting, and frontend check passes23 tests plus types/lint/format.

Repository gates are NOT GREEN: the broad Python run completed2718 passed,483 failed,4 skipped and21 errors in1:07:54 (20261028T153433.516000Z-pytest-33180-8b2f9dc1). Luna's bounded trace summary found342 CLI boundary/endpoint failures,86 authority schema failures,15 registry-binding failures, and smaller logging/presentation groups. The tree changed while workers held earlier imports, so these are historical gate results rather than a claim that483 failures still reproduce. Fresh startup and restored-schema cases pass; all remaining failed cases have not been rerun. The broad code gate failed7/14 checks, with coedited Modelo/locale syntax/import/type issues and source-read/inventory failures. Fresh configured type checking still reports coedited work-form findings; startup-test typing errors were repaired and their3 behavior cases and three-platform typing pass. Generated import inventories were regenerated. The registry gate passed earlier; no authored registry data was changed.

The exact historical Sede INTERNAL_INVARIANT, provider invalid_request and native verification subcall stall remain unattributed. Workbench completed warnings remain nested latency observations, with snapshot consistency preserved. Source uses timeout consistently for orchestration; no terminology-enforcement tests were added. Protocol4 requires matching rebuilt clients/runtime. No installation, replacement of the running Debug processes or live cold-launch acceptance is claimed.
