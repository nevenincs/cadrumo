---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0ef5a9aa8181b9e2d8ff33d13f0828fd46dbba4e5c12267629c980616bc4aca5'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]"
  - "[[2026-08-11-tui-architecture-W03-P06-S29]]"
---

# `tui-architecture` audit: `S29 resumable censal executor review`

## Scope

Formal review of `W03.P06.S29` against the amended TUI architecture decision,
the censo authority reconciliation research, and the completed `S113`, `S30`,
and `S31` contracts. The review traced exact preflight, live acquisition,
proposal construction, secure review publication, pending and consumed resume,
reject and apply effects, cancellation, irreversible mutation, cleanup,
settlement, definition typing, and facade boundaries.

The inspected implementation performs exact baseline preflight before the live
door, reacquires only in initial execution, constructs the canonical complete
intent operand, publishes through supervisor-owned secure storage at the exact
successor revision, resolves stored operands on consumed resume, enters the
irreversible section around the sole `apply_cotejo` writer, and does not export
the definition through the public user-profile facade before `S32`. Focused
operation, operand, apply, and supervisor tests passed 53 cases.

## Findings

### s29-censal-executor-review | high | Irreversible apply failures can settle with a false NONE effect

The executor enters the irreversible section while the durable operation effect
is still `NONE`, calls `apply_cotejo`, and emits `UPDATED` only after the call
returns. Any repository or post-publication exception raised after the section
is entered propagates to the generic supervisor failure classifier, which
preserves the snapshot's current effect. The terminal receipt can therefore
claim `NONE` even though the profile commit may have occurred. This contradicts
the governing requirement that storage ambiguity settle honestly as `UNKNOWN`
and makes the declared `UNKNOWN` capability unreachable on this path.

### s29-censal-executor-review | high | The executor lifecycle is not exercised by a real censo test

The S29-owned test addition constructs the request and definition but never
calls `CensalOperationExecutor.execute` or `resume`. Generic supervisor tests
prove the framework can resume a synthetic executor, while S30 and S31 tests
prove operand storage and exact apply separately; none compose the censo
executor. Consequently there is no executable proof that foreign or stale
preflight avoids authentication, acquisition happens once, publication uses the
current successor revision, pending and consumed restarts avoid reacquisition,
reject remains effect-free, apply is irreversible, or cancellation and cleanup
settle correctly. The execution record's lifecycle claims exceed its real test
evidence.

## Recommendations

Introduce an explicit fail-closed classification for exceptions arising after
entry into the profile-apply section so a possibly committed write cannot retain
`NONE`; preserve `NONE` only for proven pre-commit stale or refusal outcomes.
Add real supervisor-backed censo executor tests covering initial, pending, and
consumed paths, with call-count evidence for the public live door, exact durable
phase/effect assertions, real secure operand resolution, real profile mutation,
and cancellation/cleanup boundaries. Do not replace those proofs with mocks or
a second writer.

Close verdict: not approved. Two high findings remain; `W03.P06.S29` must not be
closed until truthful irreversible failure classification and real composed
lifecycle proofs are present.

## Remediation re-review

The re-review inspected the real composed censo executor lane and the S113
supervisor checkpoint-carry change. The focused censo, operand, exact-apply,
supervisor, and recovery selection passed 61 integration tests. Ruff,
BasedPyright, and diff integrity were clean on the reviewed surface. Pending
takeover now carries the revised durable checkpoint into the snapshot, accepts
only a response bound to that recovered revision, and resumes without a second
acquisition.

The first HIGH is resolved. The executor now persists `UNKNOWN` before the
possibly committing apply section, publishes `UPDATED` only after the writer
returns, and a real composed acknowledgement-loss test proves that a committed
profile revision followed by an exception settles failed with effect `UNKNOWN`.

The second HIGH is resolved as originally stated. Real supervisor-backed censo
tests now call initial execution and continuation, use the encrypted operand
store and filesystem journal and lease adapters, prove one acquisition across
pending takeover, bind the response to the takeover-revised checkpoint,
exercise apply and reject, and prove post-commit acknowledgement loss. The
remaining stale and cancellation effect window is recorded separately below.

### s29-stale-none-window | high | UNKNOWN before irreversible entry can misclassify proven no-write outcomes

The remediation performs the exact baseline precheck, then awaits the durable
`UNKNOWN` effect transition, then attempts to enter the irreversible section.
Those operations do not share one exclusion boundary. A concurrent profile
change after the precheck makes the canonical `apply_cotejo` stale check refuse
before mutation, yet generic failure settlement preserves `UNKNOWN` rather than
the ADR-required stale effect `NONE`. Likewise, cancellation requested after
the `UNKNOWN` transition but before irreversible entry is acknowledged without
calling the writer while retaining `UNKNOWN`. The composed tests exercise
neither stale refusal at the executor boundary nor this cancellation window.
The exact stale-precheck `NONE` guarantee is therefore neither race-safe nor
executable-proven.

## Re-review recommendations

Make the transition into ambiguity classification and the irreversible apply
boundary one ordered cancellation-safe protocol, while classifying every
proven pre-write stale or cancellation refusal as `NONE`. Add a real composed
regression that changes the profile after review and another that requests
cancellation in the pre-entry window, asserting no profile revision change and
terminal effect `NONE`.

Re-review close verdict: revision required. The two original HIGH findings are
resolved, but `s29-stale-none-window` remains HIGH. `W03.P06.S29` must not close
until the stale and cancellation no-write paths preserve `NONE` under the real
supervisor and the composed tests prove them.

## Final remediation review

Resolution: `s29-stale-none-window` is resolved. Production now performs the
exact baseline precheck while effect remains `NONE`, exposes no await between
the cancellation guard and irreversible entry other than the explicit test
seam, enters the irreversible section before publishing `UNKNOWN`, and changes
to `UPDATED` only after the sole cotejo writer returns. A cancellation accepted
at the explicit pre-entry boundary is acknowledged with `NONE` and no profile
or event-history write. A profile change between precheck and exact apply makes
the writer's second baseline check refuse; the executor restores `NONE`, and
the real history proves only the competing revision exists, with no second
censo write. An exception after the writer commits retains `UNKNOWN`, proven by
the acknowledgement-loss case.

The final focused selection passed 62 integration tests across the composed
censo executor, operand, exact apply, supervisor, and durable recovery lanes.
Ruff, BasedPyright, and diff integrity passed on the reviewed production and
test surface.

Final close verdict: PASS. No Critical or High findings remain. `W03.P06.S29`
is approved for closure.
