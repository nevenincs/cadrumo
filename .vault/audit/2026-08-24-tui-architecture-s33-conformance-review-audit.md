---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d9c20929a5a2f38df8a78120aafa51dcce95374971990afd47e3b4d916ee2d40'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S33 censal lifecycle conformance review`

## Scope

Formal review of `W03.P06.S33` against the plan row, accepted censo lifecycle,
and the live execution record. The audit inspected all six parameterized cases,
production supervisor composition, filesystem journal and lease use, encrypted
secure references and profile storage, acquisition and irreversible-boundary
seams, exact fact/divergence assertions, settlement, cancellation, and cleanup.

The focused S33 file passes six integration cases. Ruff lint and format checks,
focused BasedPyright, and diff integrity are clean. Waiting-for-review, reject,
stale refusal, detached takeover, single acquisition count, cancellation
acknowledgement, effect classification, terminal settlement, and lease release
all execute successfully.

## Findings

### s33-real-cleanup | high | The acceptance matrix replaces acquisition and proves no acquisition-resource cleanup

Every lifecycle case injects `_DeterministicCensalAcquisition`, a test stub that
returns a constructed observation instead of executing the production
`pull_censal_datos` door and its browser-session cleanup. The operation declares
no owned resource, and the tests assert only `cleanup_deadline is None` and that
the durable lease was released. Those are settlement and ownership facts, not
proof that the external acquisition resource closed before settlement. This
contradicts both the row's explicit cleanup criterion and the execution record's
claim that the cases use no fake or stub. The real persistence adapters make the
local state proof valuable, but they do not turn the substituted acquisition
into a production cleanup proof.

### s33-exact-matrix | high | Per-field cases do not assert the complete exact resulting fact set

The matrix checks adopted-path values and the set of divergence axes, but never
asserts that preserved paths are absent from effective profile facts, nor the
exact divergence artefact values and sources. An implementation that both
adopted a supposedly preserved path and emitted the expected divergence would
pass. The successful cases also do not assert exact event-history growth or the
single `CENSO_APPLIED` event. Therefore the tests demonstrate representative
outputs but do not prove the row's per-field and apply-all exactness at the
composed boundary.

## Recommendations

Replace the acquisition stub with an offline production-adapter route or a real
resource-bearing production composition whose close is directly observed after
success, refusal, cancellation, and recovery. If the external boundary cannot
be exercised deterministically, narrow neither the row nor the record: add the
production cleanup proof at its owning adapter boundary and explicitly compose
that evidence here.

For every matrix row, assert the exact contact-path fact projection, strict
expected divergence records including artefact value and source, and exact
profile event-history delta and event type. These assertions should exclude
simultaneous adopt-and-diverge behavior rather than checking only positive
members.

Close verdict: REVISION REQUIRED. Two High findings remain; `W03.P06.S33` is not
fully proven and must not close yet.

## Remediation re-review

### s33-real-cleanup | resolved | Real acquisition and supervisor-owned cleanup are now proven

The deterministic observation stub has been replaced by a loopback HTTP exchange
over the captured AEAT response and the canonical `parse_censal_datos` parser.
The acquisition returns the typed `CensalOperationAcquisition` resource contract;
the production executor registers that async resource through
`context.cleanup.own` under the definition-declared `ASYNC_TASK` family. Success,
reject/stale, and pre-irreversible cancellation paths all observe the resource
closed after settlement. This resolves the original High finding.

### s33-exact-matrix | resolved | Exact profile, divergence, and event results are now asserted

Every adopt row now asserts the exact adopted values, absence of every preserved
path, ordered divergence records with exact axis, artefact value, and canonical
source, one profile revision, and exactly one additional `CENSO_APPLIED` history
event with the expected adopted/divergence counts. Reject and cancellation retain
the exact record and history; stale application proves only the deliberately
injected competing commit occurred. This resolves the original High finding.

### s33-detach-restart | high | The composed S33 matrix no longer exercises detach or restart recovery

The apply test is named `detaches_resumes_and_cleans_up`, and the execution record
claims detach, expired-lease takeover, and checkpoint resume, but its body responds
and settles on the original `owner`. It never calls `detach`, constructs a
replacement supervisor, expires/takes over the lease, calls `reconcile`, or proves
the resumed continuation does not reacquire. A lower-level executor test does
cover checkpoint recovery and a single acquisition count, but S33 explicitly owns
the composed real-adapter lifecycle proof and the plan row expressly requires
detach and resume. The current S33 record therefore overstates its evidence.

Process-local resource ownership does not itself require combining cleanup and
restart in one impossible cross-process handle transfer. The ADR makes the
supervisor authoritative for its owned resource scope and separately requires
durable restart behavior; a replacement process cannot own the departed process's
live handle. It is valid to prove terminal cleanup on the original owning
supervisor and restart/no-reacquisition in a separate composed case using the
durable checkpoint. That separate S33 case is presently absent.

## Re-review gates

The focused S33 lifecycle file passes all six integration cases. The feasible
censo lane covering the executor, operand, reviewed apply, live acquisition, and
canonical parser passes all 61 selected unit/integration cases. No mock, fake,
patch, skip, or xfail mechanism appears in the S33 file.

Close verdict: REVISION REQUIRED. The two original High findings are resolved,
but one High conformance finding remains because S33 does not prove its required
detach/restart/no-reacquisition lifecycle.

## Final remediation re-review

### s33-detach-restart | resolved | Dedicated real takeover proves durable continuation without reacquisition

The new dedicated composed case starts the real loopback acquisition under the
original supervisor, reaches the durable review checkpoint with effect `NONE`,
proves the acquisition resource is closed, and detaches. A replacement
supervisor with an expired-owner observation then reconciles the same operation,
refreshes the pending interaction to the recovered envelope revision, consumes
a response bound to that refreshed revision, applies the stored secure operand,
and settles successfully. The acquisition count remains exactly one across
takeover, the exact adopted profile and single `CENSO_APPLIED` history delta are
observed, and the replacement's exact durable lease is absent after settlement.
This resolves the remaining High finding.

The production acquisition contract now states that a transferred resource is
idempotently closeable. The executor registers it with supervisor cleanup before
closing it at the completed-read boundary, so no process-local handle crosses a
detachable durable checkpoint; the retained supervisor registration remains the
retry/settlement path and may safely close the resource again. This is consistent
with the ADR's distinct process-local cleanup and durable-restart authorities.

## Final gates

The focused S33 lifecycle file passes all seven integration cases. Ruff lint,
Ruff format, focused BasedPyright, and scoped diff integrity are clean.

Close verdict: PASS. All prior findings are resolved and `W03.P06.S33` now proves
the required composed censo lifecycle, exact effect boundaries, restart behavior,
and resource cleanup.
