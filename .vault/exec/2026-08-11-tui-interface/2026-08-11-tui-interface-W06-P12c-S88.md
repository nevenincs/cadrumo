---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1c839b571bcbcc08455240e83adc78e1215247d10b8b30f0de4b5d96d22d4f3c'
step_id: 'S88'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S87]]"
---

# Keep modelo.work.create visibly DEFERRED under the existing work-lifecycle owner with absent-work admission, operation, atomic write-set, result-receipt, dependency, and interface reopening conditions, and prove C1-C5 cannot invoke it

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_create_deferred.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_create_deferred.py`
- `verify:` `pytest test_create_deferred.py` -> `6 passed`

## Notes

THE CLASSIFICATION HALF ALREADY HELD, so nothing was rewritten to claim credit
for it. `modelo.work.create` is classified DEFERRED in the action denominator
with an owning authority (work-lifecycle ownership), a stated reason, an
evidence reference, and a reopening condition reading "reopens only if a future
accepted decision moves this into scope". This row's contribution is the OTHER
half: proving C1 through C5 cannot invoke it.

A DEFERRAL IS EASY TO STATE AND EASY TO LEAK. An action can acquire a caller
through a dispatch row, a route, or a direct import long after the
classification was written, and nothing about the classification itself would
notice. So the proofs go wider than the dispatch table: the whole shipped TUI
package is swept for the action id, and separately walked by AST for an import
of a work-unit creation writer. Naming the id is the obvious leak; importing
the writer is the quiet one, and a deferred function-local import would not
appear in any header a reviewer reads.

DEFERRED AND PENDING ARE DIFFERENT CLAIMS, and a proof keeps them apart.
Creation must not appear in `MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS`
either: that list means "in scope for this plan, not yet built", while creation
is owned outside the plan entirely. Listing it there would misstate ownership
and invite a later reader to enrol it as though it were merely unfinished.

TWO ANTI-VACUITY CONTROLS, because an absence proof over an empty or blind
scan proves nothing. The first asserts the sweep actually finds the TUI surface
-- more than twenty modules, including `actions.py` itself. The second runs the
SAME scan against `modelo.work.rename`, an action known to be enrolled and
named by a TUI module, and requires a hit. Without it, both absence sweeps
would pass equally well against a scanner that reads nothing.
