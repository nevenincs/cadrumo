---
tags:
  - '#plan'
  - '#runtime-operation-cue-delivery'
date: '2026-11-15'
tier: L1
related:
  - '[[2026-10-27-robust-logging-adr]]'
  - '[[2026-10-17-idle-churn-operation-observation-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]'
modified: '2026-11-15'
body_schema: body-v2
body_hash: 'sha256:ee59712439e79559c9d5d873ca4d9a731c9746b535e5af1e26f4e63ca2ec2dc8'
---

# `runtime-operation-cue-delivery` plan

## Description

Approved 2026-11-15

PRIME ruling 09:20 authorizes the runtime operation cue root fix above GC work. B17 proved at least 5028 ms of a 5030 ms host tail waited for a runtime cue after settlement; it did not identify why the cue was late or lost. The faithful Windows harness identifies a concrete loss path without claiming that b17 encountered the injected fault: native signal failure leaves a false logical wake state, queued cue coalescing is not registered, later fanout is skipped, yet parent acknowledgement makes the reporter discard the batch.

In the scratch baseline a real contained worker, authorization client/server, native transport and three real observing session queues acknowledged at 47.24 ms after commit although queues were [1,1,0] and kernel signals [true,false,false]. The candidate withheld the failed acknowledgement, retained truthful signal and coalescing state, and existing retry recovered all three by 113.94 ms with one queued cue each and a fresh verified connection. No synthetic five-second delay was introduced. Preserve the diagnostic limit: this proves injected fault recovery, not the original b17 trigger.

Reuse accepted supervisor, observation and diagnostics decisions unchanged: cues are advisory, authority remains in typed operation observation, commits do not wait for cue delivery, frontend/session ownership remains intact and no periodic polling or Python fallback timer is added. This is a bounded reliability repair of existing signal/ack/retry semantics, with no new protocol fields, tax, custody, profile, authority or persistence policy. No new costly decision is introduced. Do not mix the paused GC drafts or parked projection records into this source unit.

PRIME ruling 09:52/09:56 additionally requires normal-path diagnostic timing markers at INFO in the same hand: commit callback observation, reporter send and return, exact validated worker acknowledgement receipt, parent receipt and acknowledgement write, fanout start and completed queue publication. Messages contain only fixed stage, epoch/monotonic timestamps, bounded validated opaque operation IDs and count/truncation; no request/profile data, payload, paths or exception text. INFO is gated before allocation and clocks. Capture commit observation before the reporter condition and emit outside it. Parent acknowledgement written does not mean delivered; queue publication does not mean framed or read. Markers cannot mask a primary failure, cancellation or change retry/coalescing behavior. Desktop confirmed the installed runtime root is INFO and strips overrides; emit bounded INFO observations through the existing scrubbed logger without new flags, environment forwarding or GC dependencies.

## Steps

- [x] `S01` - Repair cue publication recovery and add bounded visible INFO timing without changing timers authority or operation behavior; `src/cadrumo_client/transport/native_wake.py and new tests/test_native_wake.py, src/cadrumo_runtime/host/session_events.py and tests/test_session_events.py, adapters/worker_authorization.py and adapters/worker_authorization_client.py, new adapters/tests/test_worker_progress_delivery.py and worker_progress_delivery_fixture.py, host/operation_progress_reporter.py and tests/test_operation_progress_reporter.py, host/profile_connection_operations.py, new application/operation_cue_timing.py and application/tests/test_operation_cue_timing.py`.
- [ ] `S02` - Record the rebuilt installed cue and settlement timing and its attribution limits; `.vault/plan/2026-11-15-runtime-operation-cue-delivery-plan.md and its owning audit and ledger, native trace evidence`.

The temporary INFO recorder is strictly limited to 32 lines per opaque operation per process and 1024 retained operation budgets. A nonblocking guard drops observations on contention or exhaustion; budgets are never evicted or reset, and no cue, commit or retry uses them. After build18 attributes the tail, demote or remove these temporary observations as ordered by PRIME 10:35.

## Parallelization

S01 is sequential. Astra medium owns only the thirteen source/test paths in S01, including new test files. Terra high reviews parent fanout/hold boundaries read-only; Luna summarizes native evidence read-only. The orchestrator owns this plan/audit/ledger, integrated checks/review and exact commit/hand. No ACCEPTANCE, FRONTEND or DESKTOP edits; no GC draft dependencies. Every merge/add/commit uses .tmp/LANE-GIT.lock and exact owned staged paths. S02 follows landed native build availability and does not block a faithful-harness-proven source hand.

## Verification

Reproduce the failure first through the real Windows contained child, WorkerAuthorizationClient/Server, OperationProgressReporter, RuntimeProfileConnections, RuntimeSessionEvents and exact native SetEvent handle. Fault once during fanout after the first session is queued and the second is enqueued but not signalled. Require the old behavior to falsely acknowledge and strand the third session; the fixed path must close/refuse the failed exchange, use the existing retry/backoff and recover all sessions without an unrelated cue or Python timer. Capture monotonic commit/publication/failure/retry/ack/cue intervals and connection counts. Do not claim private injected harness times as ordinary native latency.

Test native wake logical state after failed signal and successful retry; exception-safe stream queue/coalescing and lifecycle/overflow/close behavior; duplicate partial fanout; records_changed plus operation_changed retain exactly one pending cue per kind; fresh pooled connection after failure; identity/fence/authorization refusals and report thread shutdown/backoff remain unchanged. No durable work or record effect may be repeated by cue retry. Run touched tests plus native channel readiness, operation reporter, connection cues, worker authorization and reuse coverage. Run style/format/types, configured full checker/import differential and year/complexity delta, fixing introduced findings without suppression and naming unchanged debt. The new inward runtime timing helper is enrolled through the canonical census; any regenerated output is a separate commit, listing pre-existing timing-module drift apart from the new helper. One integrated review precedes the one-source-SHA hand to INTEGRATOR alone, copying PRIME.

After landing, rebuilt native traces must separate settlement, cue emission/reception and follow completion; observe remaining uncertainty and other starvation mechanisms rather than overclaiming that this fault explains b17. Actual journal/tax results, authority and every protection remain identical. GC measurement resumes only after this priority is handled.
