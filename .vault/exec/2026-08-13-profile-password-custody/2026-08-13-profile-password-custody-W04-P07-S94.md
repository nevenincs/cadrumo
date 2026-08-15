---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a63b71c05c5b9adc02ae3d513baeb61b4e5317f05d2b5544b74bd2cf291f1c83'
step_id: 'S94'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh unwedge the supervisor-lifecycle cleanup-timeout test that hangs in an asyncio loop and takes the entire session with it under the thread-based timeout on this platform, since one wedging test denies the whole repository any sequential integration run and is therefore upstream of every measurement anyone tries to take of that lane

## Scope

- `src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py`

## Description

- Reproduce the wedge deterministically under an OS-level bound, from outside the
  repository, rather than inferring it.
- Measure which supervisor guard refuses, and correct the attribution this row and the
  file's own prose both carried.
- Freeze the cleanup-timeout proof's clock and its receipt's `settled_at` together, and
  return the cleanup window to 30ms.
- Bound the test's rendezvous on the settlement task so a settlement that refuses before
  the close begins fails instead of hanging.
- Rewrite the window comment and the test docstring against what was measured.
- Absorb a pre-existing 123-character format drift in the same file.

## Outcome

The row's premise was stale on arrival and is worth stating plainly: at HEAD the module
did not hang. All eight cases passed sequentially in 2.87s on an idle box, because an
earlier commit on this same row had already widened the cleanup window from 30ms to a
second. That earlier fix was a probability fix, not a cure — it bought headroom so the
setup would fit inside the window, and left the wedge itself intact. Shrinking the window
back reproduced the hang immediately and repeatably: the run had to be killed by an
external timeout, and the thread-based per-test ceiling printed a stack dump and then took
the process down, which is exactly how one test denies the whole lane.

The measured cause is not the one recorded. Both the earlier commit message and the two
prose blocks in the file blamed `_complete_cleanup_before_settlement` for taking an early
`now >= cleanup_deadline` exit. It does carry such an exit, but it never runs first. The
FIRST elapsed-deadline guard is `_validate_cancelled_settlement`, which sits ahead of the
owned close and ahead of the lease lock, and refuses with a `ValueError` reading "cleanup
deadline elapsed; cancellation remains unsettled" — a different guard raising a different
exception type. An instrumented probe confirmed it directly: close call count zero, the
resource never touched, `cleanup_started` never set.

Production is not at fault and is unchanged. Refusing to publish a cancelled terminal
whose cleanup window has already gone is the correct behaviour, and the supervisor neither
leaks a task nor fails to time out. The defect is in the test: it performed an unbounded
wait on an event that only the happy path ever sets, while never observing the settlement
task that had already failed. Any refusal on that path — the measured one, or the one the
prose named — leaves the coroutine blocked inside `asyncio.run` forever.

The "clock cannot be frozen" conclusion recorded alongside the earlier fix is also wrong,
and the correction is the whole fix. Freezing the clock alone does fail with "operation
exact lease expired before renewal", exactly as recorded, but not because leases read real
time. `settle` takes its `now` from `receipt.settled_at`, not from the clock, so a
wall-clock receipt measured against a frozen lease is stranded years in the future. Freeze
both and the deadline can never be spent by setup at all: settlement always reaches the
close, and the refusal arrives from the supervisor's bounded wait over a cleanup task the
resource is deliberately holding. That is the path the test is named for, reached with no
race and no dependence on machine load, in 30ms of real waiting instead of a second.

Both proofs bite. Breaking the production cleanup-deadline enforcement by runtime
monkeypatch from outside the repository reds the test in 3.28s with "DID NOT RAISE
TimeoutError"; restoring the historical wedge condition — wall clock, one-millisecond
window — now fails in 2.49s carrying the real `ValueError`, where the same configuration
previously had to be killed externally. Both patches were applied at runtime from a
scratchpad outside the tree; no tracked file was mutated for either.

## Notes

The sequential integration lane is runnable and terminates; it is not green, and none of
what is red belongs to this row. This tree is shared with concurrently working agents and
their in-flight edits are live in it. A first full sequential run aborted at COLLECTION on
an unrelated `ImportError` for `HARNESS_SRC_DIR` from `dev.locales`; re-reading the tree
showed a peer had landed that symbol between the run starting and finishing, and a re-run
collected cleanly — a reminder that a finding in this tree must be recomputed at report
time rather than trusted from when it was observed.

Seven test-framework ratchets are failing, and the type-check gate reports diagnostics
across roughly twenty files. Neither set names `application/operations` anywhere; they sit
in the registry, modelo, filing and `dev/` trees that peers are actively editing. They are
reported, not absorbed, because this row's ownership does not reach them.

The pre-existing format drift absorbed here was a 123-character line in the repositories
helper, over the configured 120 limit and already failing `ruff format --check` at HEAD.
It is unrelated to the wedge; it is in the one file this row owns, and leaving it would
have failed the format gate for whoever commits next.

`pyproject.toml` was NOT edited. The pytest timeout configuration is not implicated: the
thread-based method behaves as documented, and it cannot interrupt a blocked event loop by
design. Raising or restructuring that ceiling would have hidden the signal rather than
recovered it, so the fix was made where the block actually was.

The sibling parametrised proof in the same module was deliberately left alone. It carries
the same unbounded wait shape, but it runs on the frozen clock with a one-minute window,
so no elapsed-deadline guard can fire and it cannot reach the wedge. Widening the change
to it would have been scope this row did not ask for.
