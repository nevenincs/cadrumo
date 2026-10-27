---
tags:
  - '#audit'
  - '#runtime-connection-performance'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:bd171a36badebc194ea653b629059e2837c4f792517a44106fb220a5e642ce95'
related:
  - "[[2026-10-26-runtime-connection-performance-plan]]"
---

# `runtime-connection-performance` audit: native waits and runtime ownership

## Scope

Reviewed Python runtime hosting, Rust and Python connection ownership, cancellation, session handover, operation observation, authentication, and synthetic profile and Modelo journeys. Root implemented the changes below; three Luna 6 max agents supplied read-only review. Accepted idle-churn and operation-observation ADRs govern this work. The workspace contained substantial concurrent changes, including Rust client and Python authentication changes; these are not attributed to this patch.

## Findings

### input-thread-churn | medium | Fixed one new native wait thread per request

`src/cadrumo_runtime/host/worker_operation_requests.py` started a daemon thread for each native readiness wait. A real native-pipe regression reproduced 24 thread starts for 24 requests before the fix. `worker_service.py` now owns a two-thread executor for its independent operation and control channels. Threads block on native events, are reused, and remain separate from the application executor. Cancellation wakes and awaits the actual native wait before releasing the channel; service cleanup settles requests before joining the pool. Regression tests verify bounded thread creation, concurrent channel waits, cancellation, failure and thread termination. Independent review found no concrete cancellation or cleanup defect in this patch.

### benchmark-entrypoint | low | Fixed stale CLI journey location

`dev/ci/profile_wizard_benchmark.py` referenced a removed CLI test path and collected no tests. It now invokes `src/cadrumo/entrypoints/cli/tests/test_censo_credentials_native.py`; both baseline and candidate journeys pass.

### shutdown-test-race | low | Fixed assertion rejecting valid native channel closure

`src/cadrumo_runtime/adapters/tests/test_server_idle_wait.py` required the stop event to win against channel close during drain. Both outcomes are valid because shutdown signals and closes channels. The assertion now accepts either wake or CONNECTION_CLOSED while retaining the single-wait and prompt-drain checks. All four owning tests pass. Server behavior was not changed.

### authentication-variance | medium | End-to-end improvement is not established

Baseline first CLI invocations took 6.083 and 5.405 seconds; second invocations took 1.961 and 0.640 seconds. Candidate first CLI invocations took 14.276 and 60.082 seconds; second invocations took 1.459 and 3.451 seconds. Candidate slow-case worker operation-journal writes consumed 49.238 seconds across 76 calls, authority leases 41.070 seconds across 51 calls, and fsync 10.805 seconds across 79 calls, with little CPU. CLI invocation timings include login/setup and are not isolated authentication timings. These nested boundaries are not additive. Shared-host load, storage variance and concurrent source edits prevent a causal latency comparison. Operation-journal writes are not a direct benchmark of taxpayer-profile writes. The demonstrated improvement is bounded thread creation, not an authentication speedup.

### modelo-cost | medium | Catalogue loading and decoding warrant targeted follow-up

The synthetic Modelo 100 calculate/export journey passed in 174.087 seconds wall time with 76.984 seconds process-tree CPU. Worker calculation took 42.903 seconds; 22 catalogue loads totalled 41.656 seconds inclusive; 23 calculation-revision catalogue decodes totalled 19.234 seconds. Export took 5.579 seconds. These are nested inclusive boundaries and cannot be summed. This is baseline evidence, not a candidate Modelo comparison or proof that connection waiting dominates calculation. Any optimization must preserve authority identity, freshness and profile isolation.

### admission-contention | low | Structural risks remain hypotheses

`profile_connection_admission.py` holds a host guard through binding/storage construction and reconciliation. `profile_connection_sessions.py` serializes human handover across retiring other hosted profiles and saved-sign-in discovery. `profile_connections.py` can perform overlapping stale OS inventory observations. These are plausible scaling costs, not reproduced defects. Changing publication needs a per-profile construction fence and binding revalidation; human handover must retain its single-human-profile invariant.

### client-observation | low | No additional confirmed client defect

Python retains its verified transport and uses native event readiness; the reviewed Rust implementation uses event-driven idle input and a deadline-aware exchange queue. Rust changes were concurrent work. Standard Python and Rust operation clients reread after initial subscription, closing the usual observe/subscribe gap; no fix for that gap was warranted. Python close waiting behind an active exchange and Rust unbounded subscriber queues remain unmeasured risks, not validated failures. Local operation settlement is task/event-driven. Detached-owner observation backoff and unavailable-only reconnect waits serve recovery contracts and were not removed indiscriminately.

### stale-tui-controllers | low | Ledger test doubles lacked the current deadline contract

The broader runtime run exposed repeated failures in ledger door tests before native dispatch: fake controllers lacked `deadline`, some lacked `definition_contract`, and they were incompatible with `dataclasses.replace` in terminal observation. Root converted the six local doubles and the shared invoice harness controller into dataclasses carrying deadline and contract evidence. Shared result-read lists remain shared across copied controllers. No production deadline fallback was introduced. Focused verification covers entries, categorisation, evidence files, registers, review, import, records and invoices.

### documentation-startup-wait | low | Fixture startup polls and corpus execution has no default deadline

`dev/docs/sequences/runtime_fixture.py` waits on readiness in 100 ms increments while checking the serving future. This is a documentation fixture, not the production transport idle path. Its comment explicitly allows slow startup without an elapsed deadline. The whole-corpus helpers default to no execution timeout; the fixture owner's 25-second timeout bounds shutdown only. The two harness tests can run 281 isolated sequences plus 35 cumulative page flows, with eight page children, so long runs alone do not prove a hang. An event-driven readiness-or-terminal notification would remove polling; an overall page deadline needs an explicit ownership and cleanup policy. No fixture lifecycle change was made during the running corpus verification.

### corpus-runtime-contention | medium | Coherence exposed journal-lock and operation-deadline failures

The completed harness run passed four worker-count tests and failed both corpus tests in 2,726.73 seconds. The golden tier rejected a changed input snapshot. The coherence tier also produced runtime failures, including a 30-second operation-journal repository-lock timeout in `how-to/filing-readiness`, UNKNOWN observations and operation/result deadline failures in Modelo flows. These cannot be dismissed as input-snapshot drift. Root is reproducing the filing-readiness page alone and tracing journal lock ownership with read-only agents before assigning causality to scheduler load, concurrent client changes or an implementation defect. No deadline was extended and no UNKNOWN result was converted into success.

### journal-read-decoding | medium | Fixed avoidable read lock ownership and replay corruption race

Retained diagnostics confirmed shared journal-lock holds of 38.397 and 39.073 seconds, beyond the 30-second acquisition budget. Three failing page operations later settled after lock-related refusals. The logs do not identify which holder operation owned each long hold. Inspection found complete Pydantic record validation under the lock even for read-only snapshots, replay and observations. Root now captures raw text and performs any legacy purge under the lock, then validates the captured text after release. Mutation, inventory, idempotency and durable settlement paths retain their existing exclusion. There is no cache and no relaxed deadline or lease guarantee.

Two before-fix regressions showed a paused decoder excluding a nonblocking writer lock attempt. The final regressions cover all three read APIs: a real writer advances the journal during paused decoding while the reader returns its original coherent generation. Review also found replay could misclassify captured corruption as UNKNOWN after a concurrent deletion. A regression reproduced this; a shared presence-aware read now reports absence only at locked capture and propagates later decode errors. Five focused regressions pass. This removes one avoidable critical-section phase; it does not establish that all observed 38-second holds or load-related deadlines are solved.

## Recommendations

Keep the bounded input pool and its native regression coverage. Investigate catalogue decoding and storage/authority contention in isolated repeated runs before changing cache or locking architecture. Preserve cancellation-complete readers, UNKNOWN mutation settlement and authority checks. Run Rust owning tests against a stable revision before claiming integrated Rust verification.

## Verification

- Native thread regression failed before the fix with 24 starts for 24 requests; candidate asserts at most two and successful thread termination.
- Worker owning tests: 62 passed; after adding the dual-channel test, the four wait tests passed (63 unique owning tests across the runs).
- Native load and idle suite: 13 passed and one shutdown assertion failed; all four idle tests passed after the assertion correction.
- Native transport load, 24 roundtrips per connection: without subscriptions, p50/p95 at 1, 8, 24 connections were 0.448/0.671 ms, 5.744/10.063 ms, 17.773/30.264 ms; with subscriptions, 0.546/0.789 ms, 6.765/10.532 ms, 21.103/32.587 ms. Recorded idle CPU over 500 ms was 0 ms at timer resolution, not a claim of exact zero usage. This isolates IPC rather than authentication or profile storage.
- Ruff lint passed for the seven changed Python files; final format check passed for all seven.
- `just check-types` passed. `just check-registry-gate` passed: 58 modelos, 161 revisions, 1,502 legal references and integrity checks.
- CLI baseline and candidate: two tests passed each. Synthetic Modelo baseline passed. A candidate Modelo run and TUI end-to-end journey were not performed.
- Change-scoped gate: 1,157 CI contract tests passed, two failed in unchanged files: platform parity for the Windows WSL forwarding recipe `test-native-provisioning-linux`, and ambient temporary roots in `dev/env/browser_archive_pins.py` and `native/desktop/frontend/scripts/modelo_fixtures.py`. The gate stopped before its runtime stage. The remaining scoped stages were launched separately. The scoped serial runtime lane passed all 15 tests (4,497 deselected). Broad code, parallel runtime and harness checks are pending at this checkpoint.

Payload-free local artifacts are in `build/runtime-connection-review-20261026/`, including `review-measurements.json`, baseline/candidate traces and gate logs. They are ignored build outputs; the measurements above preserve the review conclusions in the vault. Changes overlap peer-owned uncommitted code and test prerequisites; no whole-file staging or commit was attempted.

## Continuation checkpoint

The original broad code, parallel runtime and harness tool sessions became unavailable without completion summaries; their processes were no longer present. They do not establish a completed verdict. The partial parallel log recorded 355 failures, concentrated in stale ledger controller doubles. The code aggregate was restarted into `check-code-resumed.log`; repaired fixture tests run into `ledger-fixtures.log`. The earlier completed serial lane remains valid. Overall review verdict remains PENDING while required checks are unresolved.

## Fixture repair verification

All 490 tests in the eight affected ledger modules passed in 90.72 seconds after the controller-double repair. Ruff lint and format passed for all seven fixture files. The interrupted wider run does not establish a whole-runtime verdict; the concentrated failure group is now covered by the passing focused run. Code and harness aggregate checks were restarted. Shared-host type-checking processes were active; memory exhaustion and a stalled uv cache lock were not indicated by process supervision.

## Aggregate code result

The restarted `just check-code` finished with seven of thirteen gates failing. Lint/format named the concurrently modified `dev/quality/tests/test_no_model_definitions.py`. Type checking reported 46 diagnostics across other fixture/tooling files. The import graph retained all 30 contracts and loaded 4,945 non-test modules, but its authority verdict was unavailable: the source census changed during execution and one file was temporarily unparsable. Reachability, symbol and export checks named `cadrumo.core.loopback_endpoint`, `extract_invoice_fields_from_text`, and `OptionalSourceUrl`, outside this patch. Data format, dependency declarations, secure-store writes, persistence writes, docstring references and the operation manifest passed.

An explicit `ty check` of all fourteen Python files changed by root passed after the aggregate. The earlier full type-gate pass is historical evidence from before the concurrent edits, not a claim that the current whole workspace type-checks. Two read-only fixture reviews found no blocking defect; both noted that deriving an admitted contract from the observed fixture contract would need refinement if a future test deliberately separates those identities. The current 490-test suite does not rely on that distinction.

Overall review remains PENDING: broad CI contracts fail outside this patch, the whole-runtime parallel run was interrupted, and the full corpus has no passing verdict on a stable source snapshot. Focused investigation produced the journal read-lock and replay-race fixes below; remaining write-side contention has not been shown resolved. The source changes remain uncommitted to preserve overlapping peer ownership.

## Focused contention reproduction

`python -m dev.docs.sequences check --page how-to/filing-readiness --coherence --timeout 300` passed when run alone after the broad gates finished, and passed again after the journal fix. The 30-second journal-lock failure did not reproduce in either isolated page run. This narrows the observed failure to run conditions or concurrent state; it does not prove that the lock path scales correctly or that all journal contention is fixed.

## Journal fix verification and remaining limits

The final seven-module persistence run passed all 92 tests in 72.95 seconds. It emitted three pipe-finalizer warnings in deliberate crashed-owner recovery fixtures; these are recorded rather than presented as a warning-free run. Five deterministic interleaving regressions cover load, observation and replay reads, a real concurrent writer advancing the stored revision, and corruption remaining visible after deletion. Both initial lock-ownership regressions failed before the decode split; the replay corruption regression failed before presence-aware capture was shared with replay.

Ruff lint/format and ty passed for both journal files; pyrefly and basedpyright passed for the production journal module. Independent read-only review found no remaining defect in this split. The final filing-readiness page run passed. Root changed sixteen Python files in total; the preceding fourteen-file focused type check remains applicable to those unchanged files.

The implemented improvements are bounded input-thread reuse, shorter read-side journal lock ownership, and race-correct corruption handling. Durable write-side fsync, full-history serialization, inventory/idempotency scans, catalogue decoding, and fixture readiness polling remain follow-up costs. No end-to-end authentication, profile-write, or Modelo speedup is claimed from the mixed-source, shared-host timings. Rust execution and a full TUI end-to-end benchmark remain unverified; the Rust changes reviewed were concurrent work.

## Delegated implementation and attribution checkpoint

The user authorized Sol 6.1 high workers for journal and catalogue fixes and Sol 6.1 medium for authentication/profile attribution. Root retained heavy measurement scheduling and integration ownership. All changes remain uncommitted because the working tree includes overlapping peer work.

The historical 38.397-second and 39.073-second observations are exclusive repository-lock held wall durations, not timings of individual writes or fsync calls. The old logs cannot isolate phases inside those holds. Retained failed sandboxes contain logs only, with no journal payloads or event histories available for same-record reproduction. Cumulative journal-write and lease totals from other runs cannot attribute those individual events.

S06 removes ordinary read-side legacy-purge JSON validation from shared exclusion. A legacy replacement reacquires exclusion, compares the captured bytes, and either publishes the corresponding replacement or uses one bounded locked reread/purge of the current generation. It never overwrites a concurrent successor using stale bytes. Six before/after regressions fail before the change and pass afterward; the seven-module owning suite passed 95 tests in 19.29 seconds. Scoped lint, formatting and types passed. Independent code review found no blocker. Mutation serialization, inventory/idempotency scans and durable writes remain under exclusion; full concurrent deadline resolution is not yet established.

S07 shares strict catalogue decoding across read doors, reuses the freshly captured parent context, avoids joins for absent records and decodes raw bytes directly. It adds no cross-call cache. Owning verification passed 33 tests and scoped lint/types; two regressions fail against isolated HEAD source. Independent code review found no blocker. A paired synthetic 13.4 MB catalogue probe measured median text decoding 0.322 seconds versus byte decoding 0.293 seconds, a bounded decode result only. The real native candidate journey completed in 146.839 seconds with 69.031 seconds tree CPU; the older baseline was 174.087 seconds with 76.984 seconds CPU. Shared-host and source variation prevent causal end-to-end speedup claims.

S08 adds a native profile read/edit/read journey with a new password admission for each invocation and metadata-only phase distributions. Three recorder tests, two native runs and scoped lint/types passed. The latest journey took 9.074 seconds: first login 3.089 seconds, including 2.444 seconds awaiting initial worker channel admission; later logins were approximately 216 ms. Worker password phases were 179/161/158 ms. The actual profile fact write took 57.1 ms, its nested record transaction 6.52 ms, and two SQLite commits totalled 0.179 ms. Twenty-one journal writes totalled 50.5 ms, maximum 7.55 ms; nested fsync calls totalled 15.75 ms, maximum 1.85 ms. These are configured SQLite WAL/NORMAL commits, not an fsync-per-edit guarantee. Initial worker startup includes observer imports. An earlier run was substantially slower, so no production authentication fix or speedup claim is justified by these samples.

Root's S05 recorder captures native acquisition/release clocks and nested record read/decode/serialization, lease, filesystem and logging phases without retaining payloads. Worker scope-exit publication proved insufficient: normal parent containment occurs after a drain receipt but before Python context unwinding. Benchmark-only publication now runs off-loop after successful operation drain and before the receipt; unresolved drains remain incomplete evidence. Five focused tests, lint, formatting and types pass. The corrected isolated filing-readiness run captured 122 holds; the longest was 138.721 ms, with 138.626 ms in raw record reading and zero thread CPU at clock resolution. It did not reproduce the historical 39-second holds. Eight simultaneous isolated native filing-readiness pages are the next controlled load measurement; the full original corpus still has no passing post-change verdict.

### measured-logging-under-lock | medium | Concurrent load exposes filesystem and diagnostic stalls

All eight simultaneous synthetic filing-readiness pages passed, with complete drained-worker traces and 1,028 recorded holds. The longest hold was 16.760612 seconds in commit_settlement. Subtracting immediate child spans to avoid inclusive double counting attributes 9.476251 seconds to two fsync calls, 6.842901 seconds to synchronous diagnostic emission, 0.437394 seconds to file replacement, and approximately 4 ms to all remaining work. Thread CPU was zero at timer resolution. Other lanes recorded individual fsync calls lasting 6–7 seconds. These observations measure time inside filesystem calls including possible scheduling delay, not pure hardware service time. This reproduced long holds, but not the historical 39-second event. Maximum sampled acquisition wait was only 15.1 ms; these pages do not recreate every original concurrent reader/deadline condition.

The acquisition diagnostic in held_descriptor_lock ran after acquisition and before entering the try/finally that released the lock. Besides prolonging exclusion during slow diagnostic I/O, a diagnostic exception could leak a caller-retained descriptor lock. The fix defers acquisition and release events until after unlock, preserving their order and captured durations. Five new regressions fail before the fix, including blocked sinks, exceptional protected bodies, both descriptor ownership forms and a raising sink. All 25 owning lock tests and scoped style/type checks pass. A post-fix eight-page measurement is pending at this checkpoint. The log handler itself has no explicit fsync: its measured duration may include handler and sidecar locks, rotation/metadata work, stream flush, notification and scheduling. No diagnosis of the underlying device is established.

The native Modelo comparison retains 22 full catalogue loads and 23 decodes, processing 344,095,259 bytes by recorded payload sizes. Candidate inclusive catalogue load was 16.968 seconds and decode was 15.305 seconds; these overlap. Internal guarded parent reads were reduced, but repeated full-catalogue loading remains a hotspot. The same candidate recorded a 45.047-second first frontend-password span versus 3.965 seconds worker startup and 1.814 seconds worker password handling. It cannot be attributed solely to authentication cryptography or worker startup. Additional parent admission and host-construction instrumentation is implemented; its 11 combined recorder tests and scoped lint/types pass. A serialized native rerun will locate any reproduced admission delay.

The post-fix eight-page load rerun passed every page and recorded 978 holds, no failed phase spans, and zero diagnostic-emission spans under journal exclusion. The longest hold was 1.064778 seconds; the maximum individual fsync was 0.635126 seconds. Independent review found no blocker in the lock fix. Host filesystem latency varied significantly, so the full wall-time reduction is not attributed to moving diagnostics. The deterministic blocked-sink and exception tests establish the narrower correctness and exclusion improvement.

The next native Modelo run completed in 117.232 seconds. Its first frontend login took 31.566755 seconds, with 31.047394 seconds in human admission. Channel startup finished 1.450 seconds after human admission began, while worker password processing began at 30.815 seconds and took 170 ms; bind took 6 ms. This isolates a roughly 29-second post-channel, pre-password gap. Parent preparation was 498 ms, so host construction is not the dominant gap in this run. Worker fixture/observer composition enters after the handshake and may contribute to that gap. An opt-in parent admission wall profile and separately timed worker fixture/observer setup are being added to distinguish benchmark overhead from product dispatch work.

The additional profiled journey passed in 142.131 seconds. Human admission took 18.510 seconds, fixture/observer setup 3.380 seconds, and worker password handling 2.031 seconds, including 151 ms of custody unlocking. The setup profile showed imported modules rather than an application sleep. A subsequent native journey with buffered per-call logging timing also passed. Its first human admission took 4.181769 seconds, fixture/observer setup 1.774270 seconds, worker warm imports 145 ms, password processing 189 ms, and bind 20 ms. Nine diagnostic calls finishing within that admission totalled 292 ms inclusive, maximum 283 ms. No per-log benchmark I/O was introduced: timing records publish at existing flush boundaries. Eighteen combined instrumentation tests and scoped lint/format/types passed.

The latest sample did not reproduce the earlier 29-second gap. It therefore cannot establish the cause of the earlier intermittent authentication delays or prove that production login latency is fixed. The instrumentation now distinguishes observer imports, operation-host construction, import warmup, password handling and diagnostic emission. Remaining work is storage-flush latency under load, repeated full-catalogue decoding, intermittent admission delay attribution and a stable full-corpus/Rust/TUI verification result. Overall integrated verdict remains PENDING; the bounded fixes and focused passing results above are established independently of those open items.
