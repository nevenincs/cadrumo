---
tags:
  - '#adr'
  - '#idle-churn'
date: '2026-10-17'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:e8e93b4a693a266455c699f026a6d66e233973e59ec2263e1687ac823f868994'
related:
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-10-16-idle-churn-audit]]"
---

# `idle-churn` adr: `Operation observation without polling` | (**status:** `accepted`)

## Problem Statement

Every client that waits for a registered operation polls `OperationObserve` on a fixed interval until the operation is terminal. The CLI backs off from 20 to 500 ms (`src/cadrumo_client/commands/registered_operation_observations.py:134-168`). The shared settlement helper polls every 20 ms (`src/cadrumo_client/transport/operation_settlement.py:146`). The TUI controller polls every 50 ms (`src/cadrumo_client/transport/operation_controller.py:600-629`), and the TUI operation modal every 200 ms (`src/cadrumo/entrypoints/tui/operations/modal.py:218`). The MCP attendance wait polls every 250 ms for up to 90 s (`src/cadrumo_harness/mcp/runtime_admission.py:158`). About eight more sites repeat the pattern. Each poll is a full IPC round trip that the runtime forwards to the profile worker. Completion is noticed up to one interval late. `2026-10-16-idle-churn-adr` requires every recurring check to be driven by a real signal, but its audit named only idle loops, so these active-operation loops were left out.

## Considerations

- The runtime serves one request at a time per connection and flushes pushed events only between requests (`src/cadrumo_runtime/adapters/server_connection_handling.py:207-231`). The client holds one exchange lock per connection (`src/cadrumo_client/transport/verified_transport.py:162`).
- Operations run in the profile worker. The runtime forwards observation to it (`src/cadrumo_runtime/host/operation_host.py:609`) over one of two worker channels, control and operation, each carrying one exchange at a time under its own lock (`src/cadrumo_runtime/adapters/profile_worker_transport.py:60-90`).
- The worker reaches its runtime on a private authorization endpoint that the runtime serves with up to eight concurrent connections. Each is verified once and reused for one exchange at a time under `2026-10-22-worker-authorization-channel-adr` (`src/cadrumo_runtime/adapters/worker_authorization_client.py`, `src/cadrumo_runtime/adapters/worker_authorization.py`).
- Every visible change to an operation, each non-terminal snapshot with its events and the terminal settlement, is written through `OperationJournal.commit` or `commit_settlement` (`src/cadrumo/application/operations/persistence/journal.py:402-432`), routed for durable and ephemeral operations alike by `DurabilityRoutedOperationPersistence` (`src/cadrumo/adapters/persistence/operations/durability_router.py:130-155`).
- Observation is versioned and cursor-based (`OperationObservationRequestV1`, `src/cadrumo/application/operations/frontend_requests.py:173`; `2026-08-11-tui-architecture-adr` D3).
- Cues already travel on per-connection queues, deduplicated per kind, carry no authority, and are followed by one re-read (`src/cadrumo_runtime/host/session_events.py`, `2026-10-16-idle-churn-adr`).

## Considered options

- **Keep polling, with backoff.** No protocol change, but it is a fixed-interval loop over an observable event. Rejected under the operator's ruling recorded in `2026-10-16-idle-churn-adr`.
- **Long-poll on the client's connection.** `OperationObserve` would wait, bounded, until the cursor advances. This is simple, but it holds the connection. Cancels, activity notes and pushed retirement or attendance cues would wait behind it. Rejected.
- **Runtime-held bounded wait to the worker.** The runtime would keep one worker request outstanding per observed operation. Each worker channel carries one exchange at a time, so the outstanding wait would stall every other operation or control request for the profile for its whole bound. Rejected. It was the first choice of this record, and was withdrawn when this was found.
- **The worker reports committed operations on its existing request endpoint, and the runtime cues.** After each journal commit the worker names the operation in a coalesced report. It sends the report over a verified connection to the endpoint it already uses for its own requests. The runtime cues the connections observing those operations. No runtime wait is held on a worker channel, and nothing new is opened between the processes. Chosen.

## Constraints

- `operation_changed` is a cue. It names its connection and session and carries no operation fact, cursor or authority. The client re-reads with the existing `OperationObserve`, which re-checks authority. Dedup, the queue bound and the overflow behaviour are those of the other cues.
- Only a connection that has observed the operation is cued, and only while its last observation was not terminal. A connection that disconnects, or observes the operation terminal, stops being cued for it.
- The worker's report names operation ids only and grants nothing. It is accepted only from the owned worker on its kernel-verified endpoint. It is applied only to watches in that worker's own profile.
- Reporting never delays or fails a journal commit. Reports are coalesced, so a burst of commits produces at most one report in flight and one queued. A report the runtime does not take is queued again ahead of later commits and retried after a backoff that starts at 50 ms and doubles to at most 1 s, until it is delivered or the worker closes; closing tries each pending report once. An error that ends the reporting thread itself loses the one batch that thread held, and the next commit starts a replacement; losing it is what bounds the replacements. (Amended 2026-10-17; it read "A report that cannot be delivered is dropped, not retried: the client's deadline bounds what it costs.")
- A client keeps its existing settlement deadline as the failure bound. It waits on the cue or that deadline, never on a fixed interval. Timeout is still not proof that a mutation did not commit (`UNKNOWN` is preserved).
- This extends `2026-10-16-idle-churn-adr` to active-operation observation and adds one cue to its hypothesis list. `2026-08-11-tui-architecture-adr` D3's `OperationObservationRequestV1` is unchanged.

## Implementation

We will make every client wait for operation progress through an `operation_changed` cue that the runtime publishes when the worker reports a committed change, and remove the fixed-interval observation polls.

- **Worker.** The routed operation persistence calls a commit observer after each successful `commit` and `commit_settlement`. The worker's operation host collects the reported ids, and one sender delivers them as a single batched `operations_advanced` request on the authorization endpoint.
- **Runtime.** Each `OperationObserve` reply that is not terminal records a watch for that connection, session and operation; a terminal reply or a disconnect removes it. The authorization server hands each report to the profile's connections, which publish `operation_changed` to every connection watching a named operation.
- **Client.** `FrontendClient` gains a subscription for the cue, and a lost connection wakes it as well. The CLI runner, the settlement helper, the TUI controller and modal, and the other observation loops arm before each observation and wait on the cue or their deadline. The MCP attendance wait does the same with an `attendance_answered` cue, which the runtime publishes to the asking connection when its ask is decided or withdrawn; `attendance_changed` cues the profile's holders, not the asker. (Corrected 2026-10-17 at plan close; it named `attendance_changed`, as the attendance wait's hypothesis below allowed to change.)

Hypotheses that may change within the constraints: the request and cue names; the batch bound; whether watches are keyed by connection or by operation; whether the attendance wait needs any runtime change.

## Rationale

Correctness never depended on the polls, only on the re-read each one triggered. That is why the cue pattern of `2026-10-16-idle-churn-adr` applies unchanged. Two facts decide the producer. Client connections are half-duplex, so a wait there degrades the pushes the previous decision relies on. Worker channels carry one exchange at a time, so a wait there stalls the profile. The worker's own request endpoint is already kernel-verified and owned. A report sent on it holds no wait that blocks another exchange. The journal commit is the single point every visible change passes through, so observing it there misses no event and no settlement.

## Consequences

- Operation completion is seen as soon as the worker records it, without the 20 to 500 ms lag. The round trips per operation fall from tens or hundreds to one per change.
- New protocol: one cue, one worker request kind, and runtime watch state per observing connection. Clients and runtime ship together under the pinned expected version.
- Staleness now depends on the report reaching the runtime. A report the runtime does not take arrives late, by its retry's backoff, and a waiter with no deadline, such as the operation modal, relies on that retry. (Amended 2026-10-17; it read "A dropped report shows progress late, bounded by the client's deadline.") It needs a test that commits a change and observes the cue end to end.
- Each report costs one acknowledged round trip on a verified connection. Coalescing bounds that to one in flight per worker, however often an operation commits.

Accepted 2026-10-17 on the operator's approval in this session ("1 - yes"), extending the ruling recorded in `2026-10-16-idle-churn-adr` that every recurring check is driven by a real signal.

Amended 2026-10-17 on the operator's approval in this session ("go ahead with the recommendation. amend adr and go"): the producer is the worker's report on its existing request endpoint, not a runtime-held wait on a worker channel, after the worker channels were found to carry one exchange at a time.

Amended 2026-10-17 on the operator's approval in this session ("ok add it"): a desktop that observes another manager waits for that manager's status to change instead of asking every second. The manager's pipe has a single instance and serves one exchange at a time (`native/manager/src/ipc/windows.rs`), so a held status request would block the tray, the CLI and a cutover's successor report for its whole wait; it is rejected for the same reason as the long-poll above. Instead each manager publishes its status to an owner-only record, `.runtime/manager-status/<session>.json` under its storage root, rewritten only when the status changes and naming the publishing process. The record is a cue and carries no authority: an observing desktop watches its directory, waits on the session lock's release for a takeover, and re-reads the status through the authenticated `status` request on either signal. A missing record, or one whose publisher is no longer running, means an older manager or a crashed one, and the desktop then keeps its one-second observation as the bounded fallback.

Amended 2026-10-17 on the operator's approval in this session ("go with recommendation on both"): a report the runtime does not take is retried, not dropped. The plan-close review found that the operation modal waits with no deadline (`2026-10-17-operation-cues-audit`, finding modal-waits-unbounded-on-a-dropped-report), so a dropped report could leave it showing a settled operation as running. Retrying at the producer covers every waiter and keeps the rule that a client never waits on a fixed interval. Retries run only while delivery fails, so nothing wakes while the worker is idle or once the runtime takes its reports. The Constraints and Consequences bullets are reworded in place, each with a note of what it said before.

Amended on acceptance of `2026-10-22-worker-authorization-channel-adr`: reports travel on a reused verified connection. Their content, coalescing and retry rules are unchanged.
