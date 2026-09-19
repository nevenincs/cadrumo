---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:7da332fa09590a5c1c8e19b49ff3e99e28db6d88b485b1d09d011e17a7d454e6'
related: []
---

# `tui-architecture` audit: `What the operation platform's stopping clauses can actually prove`

## Scope

## Findings

## Recommendations

## Why this exists

`W07.P16.S94` asks for cancellation at every declared cancellable phase proving
acknowledgement, cleanup completion, lock release and child-process reaping.
`S96` asks for crash and restart proving lease takeover, cursor replay, resume
policy and orphan reporting. Both name test files that do not exist, and both
have substantial coverage under other names. This records what those clauses
can actually prove against the population the registry composes, so neither row
is closed on approximate coverage nor left open for reasons nobody wrote down.

## What the composed population declares

Measured against the nineteen definitions in the production registry.

- Cancellation: seventeen `unsupported`, two `cooperative`, **zero `contained`**.
- Deadlines: seventeen `absent`, two `cooperative`, **zero `enforced`**.
- Owned resources: one definition owns an `async_task`. **No definition owns a
  `process`.**

## Clause by clause

**Cancellation at every declared cancellable phase** — for this population that
means the cooperative path, and it is covered: cancellation during a running
executor, the aggregate-deadline cooperative stop, the cleanup-deadline
escalation, heartbeat owner loss, and both detached races.

**Acknowledgement** — covered. The supervisor refuses a cancelled terminal whose
executor stopped without acknowledging, and the detached races assert the
acknowledgement is durable in the record carrying the terminal fact.

**Cleanup completion** — covered. The detached races assert the executor's
resource closed exactly once.

**Lock release** — covered. The detached races assert the lease is absent after
settlement.

**Child-process reaping** — **no subject.** No executor spawns a child process,
no definition declares `OperationOwnedResource.PROCESS`, and `contained`
cancellation, which is what would require a killable resource, is declared by
nothing. A test spawning a child inside a fixture would prove something about
the fixture, not about this system.

**Lease takeover, cursor replay, resume policy** — covered by the recovery and
replay suites: heartbeat owner loss, detach-preserving cursor replay, and an
expired resumable checkpoint restarting through real storage.

**Orphan reporting** — partially. An expired running operation reconciles to an
unknown interruption without claiming success, which is the honest half. There
is no separate reporting surface that enumerates orphans.

## The finding worth carrying forward

Three capabilities the platform models are declarable and enforced but
unexercised by any production operation: `contained` cancellation, `enforced`
deadlines, and `process` ownership. They are not dormant in the sense that
nothing implements them — the execution context refuses an executor that
acquires a resource family it did not declare — but no operation needs them.

That is the honest reason S94 cannot be closed as written: two of its clauses
describe a shape of operation this system does not currently have. Closing it
would require either an operation that owns a process, or a decision that the
row's scope is the cooperative population it actually has.
