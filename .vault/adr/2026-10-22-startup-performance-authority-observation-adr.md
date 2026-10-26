---
tags:
  - '#adr'
  - '#startup-performance'
date: '2026-10-22'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:ccbe9d6cc2847ebe17490103aa99a7afe69aa063836b54e6fd382140d436b2e5'
related:
  - "[[2026-10-22-startup-performance-request-path-audit]]"
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-10-18-runtime-authority-boundary-adr]]"
---

# `startup-performance` adr: `Authority re-checks answered from an OS-invalidated observation` | (**status:** `accepted`)

## Problem Statement

Every runtime round trip and every worker guard re-derives the same authority facts from disk and the OS: the profile lock and enrollment records, the committed password capsule and the host's full LSA logon inventory. One `facts()` costs about 40 ms on an idle host and several times that under load; a request computes it up to four times, an operation is five to eight round trips, and the worker re-reads the capsule about fifteen times per operation (`2026-10-22-startup-performance-request-path-audit`, findings authority-facts-per-round-trip and worker-binding-per-guard). The checks are required; their cost makes every operation take most of a second and the first screen about 20 s.

## Considerations

- `2026-10-16-idle-churn-adr` keeps the authority checks on every read and drives recurring observation by OS notifications; logons without a notification source are observed every 0.5 s.
- The runtime already receives WTS session notifications (`src/cadrumo_runtime/host/profile_connections.py:534`) and tracks whether every answered logon is covered by them (`_unreported_logins`).
- Custody records change only by publication into a few profile directories: `.automation-v1/<installation>/<profile>`, the bucket directory holding `profile.commit.v1.json`, and its `custody` directory. Windows reports every name, write, size, attribute and security change there through a change-notification handle whose signaled state is a kernel object read in microseconds (`src/cadrumo_runtime/host/session_watch.py:148` already uses one).
- The capsule reader states that nothing is cached between checks (`src/cadrumo/adapters/persistence/storage/custody/capsule.py:1142`); this record changes that commitment.
- The control witness also reads the Credential Manager, which has no change notification.

## Considered options

- **Keep re-reading per check, deduplicated within one request.** Removes the repeats inside a request only; the per-round-trip cost and the worker's per-guard reads remain. Rejected as insufficient.
- **A time-to-live cache.** Simple, but a revocation published by another process is seen only when the entry ages out. Rejected.
- **An observation invalidated by OS change notifications, with a 0.5 s maximum age.** A check reads from memory until the OS reports a change to the watched custody directories or the logon set, then re-reads. The maximum age bounds anything without a notification source, the Credential Manager among them, to the staleness the idle-churn decision already accepts for unnotified logons. Chosen.

## Constraints

- Every boundary that checks authority today still checks it. Only the source of the custody and logon facts changes; scope, session, generation, deadline and kernel-incarnation checks are untouched.
- An observation is re-read when any watched directory reports a change, when the WTS registration is absent or a logon's lock state is unknown, when the peer logons the runtime holds change, and when it is older than 0.5 s. An owner whose custody also lives in a store without notifications names a probe of that store, read before each re-read; an aged observation whose probe still answers the same is kept and ages again from that probe. The automation custody probes the digest of its control anchor in the Credential Manager, so an aged check costs one native read rather than the custody re-read. A logon with no lock surface, such as a batch or service logon, changes only by ending, which the lifecycle pass observes at the same 0.5 s interval, so it does not by itself force a re-read. The notification is re-armed before the re-read, so a change during the read invalidates the result it produces.
- A directory that cannot be watched (missing, unsupported platform, a failed re-arm) disables the observation for that witness: every check reads from disk as before. Failing to watch never extends a cached answer.
- A read that raises is never cached; the next check reads again.
- Writes and denials performed through the runtime or worker invalidate their own observation immediately, independent of the notification.
- The worker keeps its own observation of the capsule binding for its single profile, under the same rules.

## Implementation

We will add a custody change witness that owns change-notification handles for a profile's custody directories and answers whether anything changed since the last observation, and we will serve the runtime's lock, enrollment and binding facts, the runtime's logon inventory and the worker's capsule binding validation through it. Hypotheses that may change within the constraints: the witness's module and API, the notification filter, and whether the bucket directory is watched recursively.

## Rationale

The re-check exists to see a change published by someone else. The OS already announces every such change to the directories involved, so asking it whether anything changed answers the same question at a cost the request path can afford. The 0.5 s bound gives the one source without notifications the staleness Cadrumo already accepts elsewhere, and every failure mode degrades to today's per-check read.

## Consequences

- A runtime round trip no longer pays custody file opens or an LSA enumeration while nothing changes; the worker's guards stop re-reading the capsule.
- A Credential Manager entry removed outside Cadrumo is seen within 0.5 s rather than at the next check.
- Each hosted profile holds three directory notification handles in the runtime and the worker.
- Tests must show that a publication by another process invalidates the observation before the next check, that an unwatchable directory falls back to per-check reads, and that a raising read is not cached.

Accepted 2026-10-22 under the operator's instruction in this session: "fix the roots causes. if you have to refactor everything." The operator did not answer the follow-up question offering this option within five minutes; it is recorded as accepted on that instruction and is open to the operator's veto.

Amended 2026-10-22 on a measurement from a concurrent session: a caller-owned runtime whose owner also had a logon without a lock surface re-read the whole logon inventory on every check, about 0.9 s per profile save, because any such logon disabled holding. It read "or a logon reports no lock state".
