---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:42fb07b9c2ffd70acceb0910db8d5b72fe0ed3e9b7e040e82d0400a597cdc5f3'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `tui-architecture` audit: `s36 filed history progress review`

## Scope

Read-only review of `W03.P07.S36`, grounded in the accepted plan, ADR, research, and S34/S35 execution records. Audited the recorded filed-history executor and its focused supervisor test for safe ordered stage and unit events, refusal scope, effect truth, ownership, and real-behavior proof.

## Findings

### post-composition-progress | medium | Progress is replayable but cannot be observed while the pull is running

`FiledHistoryOperationExecutor.execute` awaits the complete canonical pull before calling `_emit_completed_unit_progress`. As a result, discovery, register access, pair walking, declaration capture, persistence, IVA-wallet, notification, and cleanup work have already finished before the first unit or refusal event is appended. The emitted sequence is result-backed and safe, but it is not live stage or unit progress under the operation identity required by S36. The test replays events only after `supervisor.start` returns, so it cannot demonstrate observable in-flight ordering.

### declaration-unit-accounting | medium | Declaration progress reports only the zero and terminal counters

The executor emits declaration progress as `0/N` and then `N/N`; it does not publish completed declaration units as the canonical capture advances. This does not provide ordered declaration-unit accounting and prevents an observer from distinguishing capture progress from a final aggregate. No duplicate capture or persistence writer was introduced.

### synthetic-discovery-proof | low | The focused integration test uses an injected discovery stub

`_local_pull` injects a nested `discover` callable that fabricates a discovery report. Although the test uses real supervisor, journal, lease, secure-reference, and sync-run persistence adapters, this stub bypasses the actual discovery progression and conflicts with the repository rule requiring real-behavior tests without fakes or stubs. It also masks the missing in-flight event timing.

## Recommendations

- For `post-composition-progress`, extend the existing canonical composition with an application-owned, safe progress/refusal reporting seam invoked at actual stage and atomic-unit boundaries; the executor should only forward those facts through its context and must not reproduce discovery, capture, or persistence.
- For `declaration-unit-accounting`, emit one safe declaration completion event per completed canonical capture, preserving monotonic counters and redaction.
- For `synthetic-discovery-proof`, replace the fabricated discovery callback with a deterministic real local adapter/fixture path and assert events become observable before later stages settle.

## Independent review adjudication

### stage-progress-coverage | high | The event stream omits the accepted filed-history stage sequence

The accepted ADR requires ordered discovery, pair, declaration, persistence,
IVA-wallet, notification, and cleanup progress, while the grounding research
also names register open, evidence persistence, filed finalization,
sync-provenance recording, and result construction. The implementation declares
only `preflight`, `execution`, `result`, and `settlement`. None of the required
inner stages becomes an operation event, so a frontend cannot distinguish a
discovery wait from register walking, an incremental write, provenance, wallet,
or notification work. This is a direct acceptance-boundary omission, not a
presentation enhancement, and independently requires revision.

The existing `post-composition-progress` and `declaration-unit-accounting`
findings are confirmed. In particular, awaiting the complete pull before
emitting `0/N` makes the initial counter temporally false as progress: the work
it describes is already complete. The later burst is a useful ordered result
summary, but it cannot be represented to users as live operation progress and
does not meet S36's row or the research requirement for live stage/unit events.

The refusal events are redaction-safe: only stable pair/stage codes and warning
severity enter the journal, never failure messages, model/year identity, paths,
URLs, or exception prose. However, declaration-scoped refusal and retryability
facts are not available, and a generic pair code cannot replace the missing
canonical unit-time reporting seam.

Effect accounting is truthful in the reviewed cases. Normal execution emits
pre-accounting `UNKNOWN`; a completed zero-write result narrows to `NONE`; clean
committed facts map to `UPDATED`; committed facts with pair/stage failure map to
`PARTIAL`; and dry-run remains `NONE`. The operation module delegates all
business stages and writes to `pull_filed_history`, so no duplicate discovery,
capture, persistence, provenance, wallet, or notification orchestration was
introduced.

The focused supervisor suite passes all eight integration cases. Ruff lint,
Ruff format, focused BasedPyright, and scoped diff integrity are clean. No mock,
patch, skip, or xfail mechanism appears. The deterministic injected discovery
port remains the only non-production acquisition boundary and, as the existing
Low finding records, cannot prove actual in-flight timing.

Close verdict: REVISION REQUIRED. One High and the existing Medium/Low findings
remain; S36 does not yet implement live ordered stage and declaration-unit
progress at canonical execution boundaries.

## Remediation re-review

The production remediation resolves the prior stage-progress and declaration-accounting findings in the reviewed executor. It passes the existing `context.events` into the canonical pull instead of reconstructing events after return, and its registered phase family now includes discovery, register access, pair walk, declaration capture, persistence, finalization, provenance, IVA-wallet, notifications, result, cleanup, and settlement. This preserves `pull_filed_history` as the sole discovery, capture, persistence, provenance, wallet, and notification authority; the executor adds no writer or frontend formatting. The final effect classifier is unchanged and remains result-backed: normal work first acknowledges uncertainty, then settles `NONE`, `UPDATED`, or `PARTIAL` from canonical accounting; dry-run stays `NONE`.

### remediation-proof-boundary | low | The focused test still cannot prove real in-flight progress

The current test continues to inject a nested discovery callable that constructs a discovery report, then replays events only after `supervisor.start` has returned. It confirms that the canonical composition receives and records selected events, but not that progress is observable before subsequent stages settle. The outstanding real-test and live-observation proof gap therefore remains.

## Remediation recommendations

- Replace the fabricated discovery callable with a deterministic real local adapter or fixture path, and hold a later canonical stage long enough to observe the earlier event through the supervisor before terminal settlement.

## Remediation verdict

Production event ownership and final effect classification pass this re-review. Revision remains required for the focused real-behavior and in-flight-observation proof.

## Focused proof re-review

The revised test structurally addresses the previous post-settlement-only assertion: it starts the supervisor concurrently, waits until discovery has entered a real `asyncio.Event` boundary, replays durable events while the start task is incomplete, and only then releases discovery before asserting the completed stream and effect. This is the correct proof shape for pre-settlement observability, and it retains the real supervisor, journal, lease, secure-reference, sync-run, and canonical composition paths.

### concurrent-replay-liveness | high | The new focused proof does not complete under sequential execution

The targeted integration run was repeated with parallelism disabled after the default selection initially deselected the integration module. The sequential `-m integration -n 0` invocation emitted only the first completed test and did not finish while the concurrent-replay scenario was pending. That scenario deliberately leaves discovery blocked, then awaits `supervisor.replay` before it can release discovery. Until that replay returns, neither the test nor the operation can advance. This leaves the remediation unverified and indicates a replay-versus-active-operation liveness problem or a test-harness wait cycle that must be resolved before the test can serve as proof.

### deterministic-discovery-double | low | The discovery implementation remains test-specific rather than a real local adapter

`_DeterministicFiledHistoryDiscoveryPort` constructs the discovery report in test code. It provides a useful asynchronous contract boundary, but it remains a test double and does not meet the repository's strict real-behavior rule against fakes or stubs. A deterministic local adapter or fixture-backed discovery path is still needed for full rule compliance.

## Focused proof recommendations

- For `concurrent-replay-liveness`, make the active-operation replay path complete without waiting for the blocked discovery work, then retain the pre-settlement assertion as a terminating integration proof.
- For `deterministic-discovery-double`, route the deterministic scenario through a real local discovery adapter or fixture boundary rather than a test-defined report producer.

## Focused proof verdict

Revision required. The test has the intended observation shape but has not completed successfully, and its discovery source remains a test double.

## Final remediation re-review

The bounded in-flight assertion resolves the `concurrent-replay-liveness` finding. It wraps the durable replay in `asyncio.wait_for` while discovery is deliberately held, confirms that the start task remains incomplete, and asserts the exact pre-settlement phase prefix before release. The focused sequential integration lane completed successfully: `8 passed in 45.34s`.

The deterministic discovery object also closes the focused proof concern in this scope. It is a concrete strict implementation of the existing narrow `FiledHistoryDiscoveryPort` seam, not a mock or patch, and leaves the canonical pull, downstream capture, persistence, supervisor, journal, lease, and secure-reference adapters on their real paths. Its purpose is to make the operation's durable-observation boundary reproducible without an authenticated external AEAT session; it does not substitute an effect writer or frontend authority.

The current implementation continues to preserve the canonical writer and result-backed effect classification. No duplicate orchestration, persistence path, or frontend-formatted event was introduced.

## Final remediation verdict

PASS. The earlier stage-progress, declaration-unit, active-replay, and focused-proof findings are resolved by the current implementation and passing focused integration proof.
