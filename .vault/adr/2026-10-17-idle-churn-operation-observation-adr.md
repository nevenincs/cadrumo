---
tags:
  - '#adr'
  - '#idle-churn'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:bd2b58b237f2e7e74732562d0d1b0bd74bf278e4d13cc887579a268191c709bb'
related:
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-10-16-idle-churn-audit]]"
---

# `idle-churn` adr: `Operation observation without polling` | (**status:** `proposed`)

## Problem Statement

Every client that waits for a registered operation polls `OperationObserve` on a fixed interval until the operation is terminal. The CLI backs off from 20 to 500 ms (`src/cadrumo_client/commands/registered_operation_observations.py:134-168`). The shared settlement helper polls every 20 ms (`src/cadrumo_client/transport/operation_settlement.py:146`). The TUI controller polls every 50 ms (`src/cadrumo_client/transport/operation_controller.py:600-629`), and the TUI operation modal every 200 ms (`src/cadrumo/entrypoints/tui/operations/modal.py:218`). The MCP attendance wait polls every 250 ms for up to 90 s (`src/cadrumo_harness/mcp/runtime_admission.py:158`). About eight more sites repeat the pattern. Each poll is a full IPC round trip that the runtime forwards to the profile worker. Completion is noticed up to one interval late. `2026-10-16-idle-churn-adr` requires every recurring check to be driven by a real signal, but its audit named only idle loops, so these active-operation loops were left out.

## Considerations

- The runtime serves one request at a time per connection and flushes pushed events only between requests (`src/cadrumo_runtime/adapters/server_connection_handling.py:207-231`). The client holds one exchange lock per connection (`src/cadrumo_client/transport/verified_transport.py:162`).
- Operations run in the profile worker. The runtime forwards observation to it (`src/cadrumo_runtime/host/operation_host.py:609`), and the worker protocol is request and reply (`src/cadrumo_runtime/contracts/profile_worker.py`).
- The worker's supervisor already awaits terminal state without polling (`src/cadrumo/application/operations/_supervisor_execution.py:268`, `:636`). The bounded `operation_settlement` action uses this for password rotation alone (`src/cadrumo_runtime/host/operation_host.py:499-546`).
- Observation is versioned and cursor-based (`OperationObservationRequestV1`, `src/cadrumo/application/operations/frontend_requests.py:173`; `2026-08-11-tui-architecture-adr` D3).
- Cues already travel on per-connection queues, deduplicated per kind, carry no authority, and are followed by one re-read (`src/cadrumo_runtime/host/session_events.py`, `2026-10-16-idle-churn-adr`).

## Considered options

- **Keep polling, with backoff.** No protocol change, but it is a fixed-interval loop over an observable event. Rejected under the operator's ruling recorded in `2026-10-16-idle-churn-adr`.
- **Long-poll on the client's connection.** `OperationObserve` would wait, bounded, until the cursor advances. This is simple, but it holds the connection. Cancels, activity notes and pushed retirement or attendance cues would wait behind it. Rejected.
- **Unsolicited worker frames to the runtime.** The worker would push "operation advanced" and the runtime would cue. This needs a new push direction on a request and reply worker protocol and its own flow control. Rejected as larger than needed.
- **Runtime-held bounded wait to the worker, then a cue.** While a connection observes an operation, the runtime keeps one bounded worker request outstanding: "return when an event after this cursor exists, or the operation is terminal, or the bound passes". On return the runtime publishes `operation_changed` to the observing connection. The client connection stays free, the worker uses its existing awaits, and cue semantics are unchanged. Chosen.

## Constraints

- `operation_changed` is a cue. It names its connection and carries no operation fact, cursor or authority. The client re-reads with the existing `OperationObserve`, which re-checks authority. Dedup, the queue bound and the overflow behaviour are those of the other cues.
- Only a connection that has observed the operation is cued, and only while it keeps observing, i.e. its last observation was not terminal. A connection that disconnects or reaches terminal ends the runtime's watch.
- The runtime's wait to the worker is bounded and re-armed. A bound expiring is not a cue. The watch never extends a lease, a session or attendance, and never delays the observing connection's other requests.
- A client keeps its existing settlement deadline as the failure bound. It waits on the cue or that deadline, never on a fixed interval. A missing cue fails as the deadline does today. Timeout is still not proof that a mutation did not commit (`UNKNOWN` is preserved).
- This extends `2026-10-16-idle-churn-adr` to active-operation observation and adds one cue to its hypothesis list. `2026-08-11-tui-architecture-adr` D3's `OperationObservationRequestV1` is unchanged.

## Implementation

We will make every client wait for operation progress through an `operation_changed` cue fed by a runtime-held, bounded worker wait, and remove the fixed-interval observation polls.

- **Worker.** A bounded `operation_wait` action returns when the supervisor records an event after the given cursor, when the operation reaches terminal state, or when the bound passes. It reports nothing beyond "changed or not".
- **Runtime.** On each `OperationObserve` that is not terminal, it arms or renews a watch for that connection and operation. One outstanding worker wait serves every connection watching the same operation. On a change it publishes `operation_changed` to each of them.
- **Client.** `FrontendClient` gains a subscription for the cue. The CLI runner, the settlement helper, the TUI controller and modal, and the other observation loops wait on the cue or their deadline. The MCP attendance wait does the same with `attendance_changed`, which already exists.

Hypotheses that may change within the constraints: the action and cue names; the worker wait's bound (about 5 s, matching `operation_settlement`); whether the runtime keys watches by connection or by operation; whether the attendance wait needs any runtime change.

## Rationale

Correctness never depended on the polls, only on the re-read each one triggered. That is why the cue pattern of `2026-10-16-idle-churn-adr` applies unchanged. The decisive constraint is that a connection is half-duplex and flushes events only between requests. Any wait on the client's own connection degrades the pushes the previous decision relies on. A wait the runtime holds toward the worker keeps every client connection free and needs no new push direction, because the worker already awaits supervisor state.

## Consequences

- Operation completion is seen as soon as the worker records it, without the 20 to 500 ms lag. The round trips per operation fall from tens or hundreds to one per change.
- New protocol: one cue, one worker action, and runtime watch state per observing connection. Clients and runtime ship together under the pinned expected version.
- Staleness now depends on the worker wait observing every event append. A missed append shows progress late, bounded by the wait's bound or the client's deadline. It needs a test that appends an event and observes the cue.
- If the worker channel cannot carry an outstanding wait alongside other requests, the worker wait needs its own channel. Reconsider the unsolicited-frame option then.
