---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c24876cb4dad604eccf990544ebdcbb8553f6af1faad8c530541c80a26ef8ace'
step_id: 'S335'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the operation modal blocking the interface event loop on a synchronous file lock, and make its detach shutdown reap the poll worker. TWO HALVES, both confirmed at their exact sites. FIRST: `OperationJournalRepository.read_observation` in the persistence adapter is an `async def` that calls the SYNC `self._repository.read_observation` inline, with no await and no offload; that sync path takes `exclusive_file_lock`, whose acquisition in `core/locks.py` is a `while True` with `time.sleep(retry_backoff)` against a deadline -- uncancellable and blocking. The modal polls it from a coroutine worker on the event loop, so a contended lock stalls the whole interface, not merely the modal. SECOND: `_request_detach` sets `_closing` and dismisses immediately, so the screen pops while the worker is still parked in its sleep or inside the read. MEASURED AND REJECTED, do not repeat: wrapping the read in `asyncio.to_thread` LOOKS right and regressed two modal tests -- `test_the_modal_renders_every_declared_fact_across_one_real_operation` and `test_rendered_state_follows_supervisor_revisions_and_never_regresses`. The modal stalls at Interaction-wait/Pending and never settles, because `_timeline` budgets 600 EVENT-LOOP TICKS calibrated against a synchronous read and a thread hop per poll needs real scheduling time that tick budget does not supply. Attribution was established by restoring both pre-fix behaviours from outside the repo: 16 passed with them, 14 passed / 3 failed without. Do NOT resolve it by widening the 600-tick budget, which accommodates the regression by loosening the assertion that caught it. Take the row's OTHER option instead: make the lock acquisition itself awaitable and cancellable, which adds no per-poll thread hop. ALSO MEASURED: `test_detach_closes_the_modal_while_the_operation_keeps_running` CRASHES its xdist worker at HEAD, with and without any change here -- 1 failed / 16 passed on reverted code -- so the second half has a pre-existing cause deeper than flag-versus-reap, and a reaper that cancels the worker and awaits it does not fix it. Diagnose that crash before claiming the detach half. NOTE deliberately NOT to encode a matcher for this shape: a rule forbidding a frontend from calling execute on an application service would match a NAME rather than a structure

## Scope

- `the operation modal's poll worker and detach path`
- `the operations journal observation read`
- `and the file-lock acquisition helper`

## Changes

- `verify:` `pytest entrypoints/tui/operations -n0` -> `22 passed`
- `verify:` `pytest entrypoints/tui/operations` (xdist) -> `22 passed, no node down, no incomplete run`

## Notes

No file changed. Both halves are implemented, and the row reads as open work
because it was written before they landed.

FIRST HALF, the blocking read: `core/locks.py` already ships
`exclusive_file_lock_async`, an awaitable twin that waits on `asyncio.sleep`
rather than `time.sleep`, with the identical deadline and refusal and NO
executor hop -- exactly the shape this row prescribes and explicitly not the
`asyncio.to_thread` form it measured and rejected.
`OperationJournalRepository.read_observation` acquires through it
(`journal.py:323`), and its docstring gives this row's own reasoning: the sole
caller is a UI poll worker on the interface event loop, so a synchronous
acquisition parks that loop for the whole contention window. The remaining
synchronous `exclusive_file_lock` calls in that module belong to the sync
repository and are not on the poll path.

SECOND HALF, the detach reap: `_request_detach` no longer flags and dismisses.
It awaits `_stop_poll_worker()` before `dismiss`, and the comment states why --
flagging alone let the screen pop while the worker was still parked in its
sleep or inside the observation read, so teardown raced a live poller.
`action_request_close` reaps for the same reason.

THE CRASH THIS ROW SAYS BLOCKS THE SECOND HALF NO LONGER REPRODUCES, and that
was checked the way the row frames it rather than only the convenient way.
`test_detach_closes_the_modal_while_the_operation_keeps_running` is recorded as
CRASHING ITS XDIST WORKER at HEAD, independent of any change. Run serially it
passes, which alone would not settle the question -- the row's claim is about
xdist specifically. Run UNDER xdist the whole module is also green: 22 passed,
no `node down`, and the lost-test reporter raised no incomplete-run banner, so
the pass covers every collected test rather than the survivors of a dead
worker.
