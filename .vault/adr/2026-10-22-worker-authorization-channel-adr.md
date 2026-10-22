---
tags:
  - '#adr'
  - '#worker-authorization-channel'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:dea63f6f09f0314110bb017787e0f4e90c4e7d8a4fae03543d218ac159f4a594'
related:
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-10-22-startup-performance-authority-observation-adr]]"
  - "[[2026-10-22-startup-performance-request-path-audit]]"
  - "[[2026-10-18-runtime-authority-boundary-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-14-mcp-purpose-authentication-renewable-stage-permits-adr]]"
---

# `worker-authorization-channel` adr: `Reused verified worker authorization connections` | (**status:** `accepted`)

## Problem Statement

The profile worker opens a new native connection to its runtime parent for every authorization exchange: each stage permit, each body-less authority check, each approval phase and each progress report (`src/cadrumo_runtime/adapters/worker_authorization_lease.py:94-139`, `src/cadrumo_runtime/adapters/worker_authorization_client.py:85-117`). Each connection repeats full kernel peer verification on both ends and a version handshake before its single exchange (`src/cadrumo_runtime/adapters/worker_authorization.py:178-182`, `:416-432`; `src/cadrumo_client/transport/windows_channel.py:36-79`).

An external harness measured one TUI profile field save on a real-sized profile. These are operator-supplied observations of 2026-10-22; no vault record holds them yet.

- The save ran 6 durable operations: 1 mutation and 5 profile-view pages.
- The runtime saw 72 worker handshakes, 72 `WorkerAuthorityEnvelope` frames, 45 permit, instruction and released cycles, 27 `WorkerOperationsAdvanced` reports and 28 `ProfileWorkerRequest` frames on the held runtime-to-worker channels.
- py-spy on the uninstrumented runtime put `WorkerAuthorizationServer._connection` at about 48% of runtime busy CPU. In the worker, `_verified_parent_channel` took about 10% and `WorkerAuthorizationLease.acquire` about 12% of busy CPU.
- Database work was 6.5 ms and fsync 54 ms, against 1.5-2 s wall time for the save.
- The harness also counted 5,292 `_sid_text_valid` and 1,008 `_object_bytes` calls per save in `src/cadrumo_client/transport/windows_desktop_logon.py`.

The authorization protocol, not tax work, dominates the save. The connection lifetime between worker and runtime is a protocol commitment. `2026-10-17-idle-churn-operation-observation-adr` currently describes it as one fresh connection per report, so changing it needs a decision.

## Considerations

- No accepted record chose one connection per exchange; the code took that shape. `2026-10-17-idle-churn-operation-observation-adr` describes it and builds its report producer on it.
- `2026-10-16-idle-churn-adr` already settles the rule for long-lived service connections. The image is verified at admission. Before each later request the runtime proves the admitted peer's kernel incarnation: pid, creation time, retained handle and channel peer. The image is verified again whenever the incarnation differs.
- A Windows channel retains the peer process handle and rechecks its incarnation in microseconds (`src/cadrumo_client/transport/windows_channel.py:86-145`). POSIX channels recheck through a pidfd or an audit token (`src/cadrumo_runtime/adapters/native_peer.py:12-31`). A pipe or socket instance cannot change its peer process, so the runtime boot id proven at the handshake holds for the connection's life.
- The runtime thread serving a connection holds the profile's admission fence through a COMMIT body, because the profile RLock is thread-affine (`src/cadrumo_runtime/adapters/worker_authorization.py:104-110`, `:203-219`). Approval publication, runtime-server start and model runs execute on that thread and channel.
- A channel lost while a permit is outstanding is an effect body of unknown state, and the worker is contained (`src/cadrumo_runtime/adapters/worker_authorization.py:220-236`). Rule 00 keeps containment owned through settlement and ambiguous effects `UNKNOWN` or `SETTLING`.
- `2026-09-26-mcp-purpose-authentication-profile-access-adr` requires newly admitted authority for every executing stage and releases access while waiting. Rule 00 requires a recheck at private submission, effects, interaction responses and disclosure. Each recheck is `RuntimeProfileHost.authorize` in the runtime (`src/cadrumo_runtime/host/profile_host.py:416-441`), independent of the connection that carries it.
- The runtime serves at most eight concurrent connections per worker (`src/cadrumo_runtime/adapters/worker_authorization.py:137`, `:151`).
- `OperationAuthority.require` runs a full guard with an empty body: a point check that holds nothing (`src/cadrumo_runtime/host/operation_authority.py:454-468`). Every guard costs a request and permit round trip, a release and released round trip, and an acknowledgement (`src/cadrumo_runtime/adapters/worker_authorization_lease.py:251-281`).
- The desktop-logon witness is not on the worker channel path. In the current tree it is reached from login capture and observation (`src/cadrumo_runtime/adapters/windows_login.py:73-126`, `:129-173`). `2026-10-22-startup-performance-authority-observation-adr` governs that cost, and `src/cadrumo_runtime/host/profile_connections.py:79-98` now serves it from a held observation.
- `2026-10-22-startup-performance-plan` Step S06 pre-starts an unbound profile worker. It is in flight, owns `src/cadrumo_runtime/adapters/profile_worker*.py` and `src/cadrumo_runtime/host/worker*.py`, and its own ADR is not yet written.

## Considered options

- **Keep one connection per exchange and make verification cheaper.** For example, cache the image path per incarnation and drop duplicate checks. The 72 pipe instances, accept hand-offs and handshakes per save remain. Rejected as insufficient.
- **One connection per operation, from submission to settlement.** About six handshakes per save remain. Progress reports belong to no operation. An operation's concurrent stages, such as execution and an observer's disclosure guard, need more than one connection anyway. Rejected.
- **One multiplexed channel for the worker's lifetime.** Exchanges interleave by request id. It needs a demultiplexing reader and moves the COMMIT fence off the connection's thread. A chunked model-run body or approval secret blocks every other stage behind it. One framing fault ends every outstanding permit and contains the worker. Rejected.
- **A pool of reused verified connections, one exchange at a time on each.** The worker keeps verified connections open and checks one out per exchange. The runtime serves the next exchange on the same connection after the previous one ends. Identity is verified once per connection, and the kernel incarnation is rechecked before every exchange. The exchange protocol, the fence's thread, containment and the eight-connection bound are unchanged. Chosen.
- **One permit per operation, or a permit kept across guards.** It removes most permit cycles. Authority would no longer be admitted at each stage, and a revocation between stages would be seen late. Rejected because it weakens the guard.

## Constraints

Binding commitments:

- **Admission per exchange.** Every permit, response scope, inventory read, approval phase and check is admitted when it arrives, exactly as today. A connection carries no authority, session or permit between exchanges. Reusing a connection never reuses an admission.
- **One exchange at a time per connection.** An exchange runs to completion on the runtime thread serving its connection. That includes a held COMMIT fence, its instructions and its release. The fence is released before the connection waits for its next exchange.
- **Identity once, incarnation every time.** When a connection opens, the runtime verifies the worker's pid, OS owner, job membership and version handshake, and the worker verifies the runtime's pid, OS owner, storage identity and boot id. Before every later exchange, the runtime rechecks the worker's incarnation through the retained handle and its membership in the owned job. The worker rechecks the runtime's incarnation the same way. Any mismatch refuses the exchange and closes the connection.
- **Reuse only after a clean end.** A connection returns to the pool only after an exchange that reached its terminal frame on both sides: release acknowledged, refusal acknowledged, report acknowledged, or approval phase acknowledged. A timeout, frame error, cancelled exchange, partly consumed secret frame or any other exception closes it.
- **Containment unchanged.** A channel lost while a permit is outstanding contains the worker before the fence drops. A channel lost while idle contains nothing, because nothing is outstanding.
- **Revocation unchanged.** Sign-out, lock, retirement and revocation refuse the next admission. They do not need to close idle connections. Runtime stop wakes every idle connection, and each closes.
- **Bound unchanged.** The runtime serves at most eight connections per worker. The worker opens no more than that in total, idle and busy together.
- **One bound identity.** Connections belong to one worker id, runtime boot id and profile binding. They open only after the binding exists and close when the worker is retired, unbound or rebound. A pre-started unbound worker holds none, and no connection opened before a binding serves after it.
- **Progress reports keep their rules.** `2026-10-17-idle-churn-operation-observation-adr` still governs them: ids only, no authority, never delaying a commit, coalesced to one in flight and one queued, retried on failure. Only their transport changes, to a reused connection. A report is never combined with an authority frame.
- **No permit coalescing.** No permit spans stages, actions or guards. A body-less check may use a check-only exchange instead: the runtime evaluates admission and answers allowed or refused in one round trip, holding no fence and issuing no permit. It is used only where no body runs under the result.
- `UNKNOWN` and `SETTLING` semantics, exchange deadlines and refusal codes are unchanged.

Implementation hypotheses that may change within these constraints:

- Pool size and idle retention, for example keeping up to two idle connections and opening more on demand up to the bound.
- Whether progress reports share the pool or use one dedicated connection.
- Whether the acknowledgement after `WorkerAuthorizationReleased` stays, or the next request on the connection stands in for it.
- The check-only exchange's frame names.

## Implementation

We will make the profile worker reuse verified authorization connections to its runtime parent, one exchange at a time on each. Peer and runtime identity are verified once per connection, and the kernel incarnation before every exchange.

- **Worker.** `WorkerAuthorizationClient` owns a bounded pool of verified connections. A lease, an inventory read, an approval phase and a progress report each check one out, run today's exchange, and return it only after a clean terminal frame. `OperationAuthority.require` uses the check-only exchange.
- **Runtime.** `WorkerAuthorizationServer._connection` loops. After an exchange ends cleanly it waits for the next envelope on the same channel, woken by stop, and rechecks incarnation and job membership before reading it. Full verification and the handshake run only when a connection is accepted.
- **Sequencing.** Implementation starts after S06 of `2026-10-22-startup-performance-plan` closes, or under that plan's orchestrator. S06 changes when a worker receives its identity and owns the worker entry files.

## Rationale

The cost is connection setup, not authority. Admission already runs per exchange in the runtime, which is what the authority invariants require. The pipe instance, accept hand-off, token and image reads and handshake prove facts that cannot change for one pipe instance unless a process ends, and the incarnation recheck detects that. Reuse removes the repeated setup and leaves every admission, the fence's thread, containment and the concurrency bound where they are. It applies the incarnation rule `2026-10-16-idle-churn-adr` already accepted for service connections, so it adds no new trust argument. Multiplexing saves the same setup but rewrites the protocol and adds head-of-line blocking and shared failure. Per-operation connections leave most of the setup in place. Permit coalescing saves frames by weakening the guard.

## Consequences

- Handshakes per save fall from 72 to at most the pool size, paid once per worker lifetime. On a warm connection a permit cycle costs two round trips, a check one, and a progress report one. The effect on the measured runtime and worker shares must be measured again with the same harness.
- The desktop-logon witness counts are outside this record. Re-measure them on the current tree, which includes the held login observation. Route any remaining cost to `2026-10-22-startup-performance-authority-observation-adr`.
- The runtime keeps up to the pool size of threads blocked per worker while idle. They wake on stop or peer loss and use no CPU.
- Tests must cover: reuse after a clean exchange; closure after a timeout, frame error, cancellation or partly read secret frame; refusal on an incarnation mismatch; containment when a channel with an outstanding permit is lost, and none when an idle one is lost; a revocation between two exchanges on one connection refusing the second; runtime stop closing idle connections; and a check-only exchange that refuses on failed admission and grants no fence.
- Both sides of the protocol change: the connection loop and the check-only exchange. Worker and runtime ship together under the pinned version.
- Reconsider if a platform cannot recheck a peer's incarnation without repeating full verification, or if measurement after the change shows admission rather than setup dominating.

## Amendments to other records

Applied on acceptance.

- **`2026-10-17-idle-churn-operation-observation-adr`.** Reword in place, then add one amendment line.
  - Considerations, third bullet. New text: "The worker reaches its runtime on a private authorization endpoint that the runtime serves with up to eight concurrent connections. Each is verified once and reused for one exchange at a time under `2026-10-22-worker-authorization-channel-adr` (`src/cadrumo_runtime/adapters/worker_authorization_client.py`, `src/cadrumo_runtime/adapters/worker_authorization.py`)."
  - Considered options, chosen bullet. Replace "It sends the report on a fresh connection to the endpoint it already uses for its own requests. The runtime cues the connections observing those operations. No channel is held, and nothing new is opened between the processes." with "It sends the report over a verified connection to the endpoint it already uses for its own requests. The runtime cues the connections observing those operations. No runtime wait is held on a worker channel, and nothing new is opened between the processes."
  - Rationale. Replace "The worker's own request endpoint takes one connection per request and is already kernel-verified and owned. A report sent on it holds nothing open." with "The worker's own request endpoint is already kernel-verified and owned. A report sent on it holds no wait that blocks another exchange."
  - Consequences, last bullet. New text: "Each report costs one acknowledged round trip on a verified connection. Coalescing bounds that to one in flight per worker, however often an operation commits."
  - Added line: "Amended on acceptance of `2026-10-22-worker-authorization-channel-adr`: reports travel on a reused verified connection. Their content, coalescing and retry rules are unchanged."
- **No change, with the reason:**
  - `2026-10-16-idle-churn-adr`: this record applies its incarnation rule to worker connections.
  - `2026-10-22-startup-performance-authority-observation-adr`: the sources of admission facts are unchanged.
  - `2026-10-18-runtime-authority-boundary-adr`: worker custody and authority stay in the runtime.
  - `2026-09-26-mcp-purpose-authentication-profile-access-adr`: every stage is still newly admitted, and waiting still holds no access.
  - `2026-10-04-runtime-manager-architecture-adr` and `2026-10-04-runtime-manager-architecture-supervisor-contract-adr`: containment and native peer identity are unchanged.

Accepted 2026-10-22 on the operator's approval in this session ("go", in answer to accept, revise or reject this record). S06 of `2026-10-22-startup-performance-plan`, the sequencing precondition, had closed.
