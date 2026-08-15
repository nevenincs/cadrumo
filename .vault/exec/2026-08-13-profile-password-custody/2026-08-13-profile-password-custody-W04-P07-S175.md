---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:7419b6d4be2eae9197d4907b0422d63674edcffe74a6876d7cc005ccc80c6386'
step_id: 'S175'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the supervisor declaration guards that now fail open, since three contract tests asserting a refusal of undeclared event claims and undeclared resource ownership all report that no refusal was raised at all, every production module in the package being byte-identical to the recorded baseline so the guards were not removed but stopped biting, and a guard that fails open is a worse failure mode than the crash whose investigation surfaced it

## Scope

- `src/cadrumo/application/operations/`

## Description

- Measure all three failures with an out-of-repo instrumentation probe before forming any conclusion, capturing whether the guard is reached, what it compares, the actual compared values, and the byte-exact journal state at the moment the guard decides.
- Trace the shape change to its introducing commit with `git log -S` over the absorbing handler rather than inheriting any recorded attribution.
- Introduce `OperationDeclarationError`, a `ValueError` subclass raised by all four definition-admission guards in `_execution_context.py` and by the terminal-receipt effect guard in `_supervisor.py`.
- Re-raise that type ahead of the blanket executor-failure handler at both executor-driving sites in `_supervisor.py`: `start` and `_resume_from_checkpoint`.
- Promote the new type to the package facade `__all__` so a caller of `start` can catch a declaration breach distinctly, and enrol `_execution_context` in the facade import-boundary gate.
- Re-found the one supervisor test that asserted the opposite outcome for the same input, keeping its four-way parametrisation (it is the only coverage of the undeclared interaction-kind guard).
- Prove the restoration bites in both directions and prove the journal is untouched on the refusal path.

## Outcome

### Measurement, before any conclusion

All three failures were instrumented from a scratchpad script that wraps the guards and the absorbing handler, so nothing under `src` was edited to observe. Every one of the three reported the same measured sequence: the guard is REACHED, the guard RAISES, and the refusal is then absorbed by the supervisor.

- Undeclared phase: claimed `operation.phase.undeclared`, definition declares `('operation.phase.declared',)`; guard raised.
- Undeclared effect: claimed `updated`, definition permits `none` and `unknown`; guard raised.
- Undeclared resource family: claimed `async_task`, definition declares an empty owned-resource set; guard raised.

In every case `start` propagated NOTHING to its caller. The operation was instead settled to `terminal`, revision 2, event cursor 3, with a `FAILED` receipt and an appended diagnostic plus terminal event; the on-disk journal grew from 896 to 4763 bytes.

The three structurally different breaches produced one identical diagnostic reference, because the correlation digest folds the exception TYPE, and all three were a bare `ValueError`. A developer reading the journal could not distinguish an undeclared phase from an undeclared effect from an undeclared resource family, nor any of them from an unrelated `ValueError`.

### Per-failure ruling

All three fall under one explanation, and it is none of the three offered candidates cleanly. The guard is intact, reached, and comparing the right things against the right declarations, so this is not a stale precondition and not a changed declaration shape. The test also still constructs a genuinely undeclared case, so it is not a stale test construction either.

The actual explanation: a later deliberate design decision changed the DELIVERY SHAPE of every executor-originated exception, and its blanket `except Exception` net over-captured the supervisor's own admission guards. The introducing commit is `0a2c103b4c`, which wrapped the executor await in `start` and did not touch the contract module; its recorded verification ran only the supervisor, models and events modules, so the module that gated the guards was never re-run. The contract module was edited once afterwards, for an unrelated permitted-effects widening, which is why the breakage survived a later touch of the same file.

The parametrised pair and the resource-ownership case do not differ: all three share one cause and one remedy.

### The collision, and why the ruling went this way

The same commit also authored a supervisor test asserting the OPPOSITE contract for exactly these four undeclared executors, so two tests in one package demanded contradictory outcomes for the same input. Satisfying either reddened the other, which is the oscillation signal that neither shape as written was right.

The ruling is grounded in the introducing commit's OWN accepted assertions, not merely in the older contract:

- Its suite already asserts that a declaration breach detected at settlement refuses and propagates BEFORE cleanup or journal mutation. A declaration breach detected inside the executor was normalising instead, so the normalisation contract was internally inconsistent about declaration breaches.
- Its suite already asserts that cancellation crosses the executor boundary, propagates, invents no terminal artifact, and leaves the operation for later explicit settlement. A propagating, non-settling exit from `start` was therefore already a sanctioned shape, not a novelty introduced here.

So declaration breaches are now uniform: they always propagate and never settle, wherever the supervisor detects them. Every other executor exception still normalises exactly as before. The normalisation property retains independent coverage through the registered-refusal, registered-non-refusal, and unexpected-failure proofs, none of which were touched.

The rejected alternatives: leaving the normalisation in place and re-founding the contract module would have made a definition-contract defect indistinguishable from a runtime failure at the one boundary that can name it, and would have contradicted the settlement-side declaration guard in the same package; settling AND propagating would have satisfied neither, since the contract explicitly requires the journal to stay inert. There is no production consumer of `start` yet, so the choice carried no caller-breakage cost either way and was decided on merit.

### Two-way bite proof

The restored refusal was proven to bite in both directions with real adapters, a real encrypted operand store, and a real filesystem journal.

- Refuses: each of the three undeclared claims now propagates `OperationDeclarationError` out of `start`.
- Accepts: an executor claiming a DECLARED phase, a declared effect and a declared resource family completes all three claims, propagates nothing, and leaves the operation running with its phase and effect events durably recorded. A guard that refused everything would have been caught here.
- Does not over-reach: an ordinary executor failure unrelated to any declaration still normalises to a terminal `FAILED` receipt with its opaque correlation digest, so the newer contract is preserved for the class it was written for.

The gates themselves were proven to bite by breaking production at runtime from an out-of-repo pytest plugin, with no tracked file mutated. Neutralising the supervisor re-raise clause reddened all seven gates; independently making the guards raise a plain `ValueError` again, so the narrow clause no longer recognises them, reddened the same seven. Both mutations were reverted by process exit.

### The journal clause

The journal clause was verified as a contract term, not read off the passing assertion. The probe captures the byte content of every journal and lease file at the exact moment the guard decides, and compares it against the same files after the refusal has propagated: identical for all three cases. The persisted snapshot after refusal is running at revision 1, event cursor 1, carrying only the `operation.started` notice, with no terminal receipt.

This is a second finding against the prior state, and the worse half of it. Before the remedy the refusal path was not merely failing to announce itself: it was writing a terminal receipt and two events into the durable journal, so a definition-contract defect was being recorded as an operator-facing operation failure. That is now gone.

### Verification

The package baseline of 53 passed and 3 failed under `-m integration` was reproduced independently before any edit; the three failures were exactly the row's three.

- `src/cadrumo/application/operations` under `-m integration` with `-n0`: 56 passed, 0 failed. Before: 53 passed, 3 failed.
- `src/cadrumo/application/operations` and `src/cadrumo/adapters/persistence/operations` under `-m "unit or integration"` with `-n0`: 252 passed, 0 failed.
- Scoped Ruff check passed and Ruff format reported all five changed files already formatted.
- Scoped BasedPyright over the five changed files reported 0 errors, 0 warnings, 0 notes.

Every run passed `-m integration` explicitly; the repository's default marker selection would otherwise have executed zero tests in this package and printed green.

## Notes

Two tree-wide gates are red, and neither is attributable to this work. The import-hygiene gate reports one production and many test-only cross-package private imports, all in profile-custody, user-profile, modelo, workflow and TUI paths; the operations package appears nowhere in its output. The docstring core-struct link gate reports 49 pre-existing module-to-struct uses lacking a cross-reference; its single operations-named entry is in the persistence adapter package, not in any file changed here. Neither was absorbed.

The row's remedy overturns the outcome asserted by an earlier accepted and independently reviewed step for the four undeclared-executor cases. That step's decision was not wrong about its own subject, executor failure normalisation, which is preserved intact; its blanket handler simply captured a class of fault it was not written for. This reversal is deliberate, is grounded in that same step's other accepted assertions, and is reported to the campaign rather than left implicit in a green suite.

The shared scratchpad directory is used concurrently by other sessions, and the bite-proof plugin file was overwritten by a peer partway through. Both bite proofs had already been executed and their full output captured to separate log files before that happened, so no evidence was lost.

No commit, stage, stash, reset or checkout was performed, and the plan row was not checked.
