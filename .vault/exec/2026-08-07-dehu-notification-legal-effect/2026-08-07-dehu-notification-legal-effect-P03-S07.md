---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b720a160e9673dfd037788fe938b1dd404de81fb9c33bcc8a780281e6a9fa6ff'
step_id: 'S07'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Widen the actionability predicate behind actionable_post_filing_events so an event is actionable when its post_filing_kind is in ACTIONABLE_POST_FILING_EVENT_KINDS or its notificacion_estado_servicio is RECHAZO_TACITO, then add a mutation-proof test proving a plain NOTIFICACION event carrying RECHAZO_TACITO state appears in actionable_post_filing_events and that reverting the widening back to a bare frozenset membership check fails the test

## Scope

- `src/cadrumo/application/overview/_calendar.py`
- `src/cadrumo/application/overview/tests/`

## Description

- Extract the attention predicate into a named helper carrying two independent
  limbs, and widen it so an event is actionable when its procedural kind is an
  actionable category OR its service state is the deemed-served one.
- Keep the second limb keyed on the deemed-served VALUE rather than on the
  field being populated, so the surface does not regress to flagging every
  projected notification.
- Add the coverage that proves both directions, plus an in-suite anti-tautology
  proof reproducing the pre-widening predicate, and prove the suite bites by
  reverting the widening at runtime.

## Outcome

A plain notificacion whose concepto matches no sharper procedural pattern now
reaches the operator once its Ley 39/2015 art. 43.2 window has lapsed. That row
was previously actionable on no day at all: the generic fallback category is not
a member of the actionable set, so the taxpayer bore a notification's
consequences with the application never saying so.

The widening is additive, not a replacement. A read requerimiento inside its
window is still actionable on its category alone, and that is asserted rather
than assumed, guarding against a rewrite that substituted one limb for the
other.

## Verification

    uv run --no-sync pytest src/cadrumo/application/overview/tests/test_calendar_notificacion_estado_servicio.py -n0 -q
    10 passed in 14.21s

    uv run --no-sync pytest src/cadrumo/application/overview/tests/ -n0 -q
    245 passed in 29.35s

Mutation proof, run with a plugin loaded from OUTSIDE the repository. The
mutation restores the exact pre-widening shape: a bare frozenset membership test
on the procedural kind, with no service-state limb.

    PYTHONPATH=<scratchpad> uv run --no-sync pytest src/cadrumo/application/overview/tests/test_calendar_notificacion_estado_servicio.py -n0 -q -s -p revert_actionability_widening
    MUTATION HOLDERS FOUND: ['cadrumo.application.overview', 'cadrumo.application.overview._calendar', 'cadrumo.application.overview.tests.test_calendar_notificacion_estado_servicio']
    MUTATION APPLIED TO: [all three]
    STILL ORIGINAL AFTER REBIND: []
    2 failed, 8 passed in 15.36s

Both deemed-served assertions went red; every negative control stayed green,
which is what makes the mutation targeted rather than merely destructive. The
plugin enumerates its holders before and after rebinding and asserts none
remains original, so a no-op rebinding cannot read as a passing proof.

    uv run --no-sync ruff check src/cadrumo/application/overview/
    All checks passed!

## Notes

A first version of the mutation plugin iterated a snapshot of the module table
and reported two holders where three exist, which would have understated its own
reach. The corrected plugin enumerates holders explicitly and asserts the
post-rebind set is empty of originals. The verdict was unchanged, but the
instrument was checked rather than trusted because it had reported a number that
did not match the tree.

The core package facade acquired unrelated peer work in progress while this Step
ran. It was excluded by explicit pathspec and left untouched.
