---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:5ff47cbb144720138f48986139c894e1f46c54d5a9feb4f69a2d8aa030d4277e'
step_id: 'S445'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Separate naming the deferred create action from reaching for it, and give the calendar recovery invariant a home on its model. The TUI mention the gate reds on is a validator that REFUSES any recovery action other than the canonical create, which is the opposite of a leak. Move the same invariant onto the entry model so direct construction is checked too, keep the controller check because model_copy skips validators, and narrow the gate to an enumerated sanctioned mention rather than deleting a live refusal to make it green.

## Scope

- `src/cadrumo/application/modelo/declarations_calendar.py`
- `src/cadrumo/entrypoints/tui/modelo/tests/test_create_deferred.py`
- `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`

## Changes

61 passed. The gate is green, and the route there was wrong twice before it was
right, which is the part worth recording.

WHAT THE MENTION ACTUALLY IS. declarations/controller.py names the create action
inside a validator that RAISES unless a calendar recovery action is exactly the
canonical create bound to its own address. It never invokes it. The gate scans
raw text as a proxy for "reaching for the action", and a refusal is the opposite
of reaching -- the proxy's false positive.

FIRST ATTEMPT, WRONG. The same invariant already existed in the projector, so
the controller looked like pure duplication and I deleted it. A TUI test then
failed, and the reason it failed is the finding: it builds its bad entry with
`model_copy(update=...)`, which in pydantic v2 SKIPS validators. So an entry
mutated that way reaches the controller with nothing having checked it, and the
controller was the only thing catching it. Deleting it traded a live check for a
green gate.

SECOND ATTEMPT, ALSO INCOMPLETE. I moved the invariant onto the entry model,
which is a real improvement -- the projector validated only what it built, while
a frontend receives the MODEL, so a projection constructed directly reached the
screen unchecked. But breaking that model validator did not fail anything: every
existing test goes through the projector, whose own check masks the model's. The
new validator was unexercised, which is the "gate that cannot fail" shape.

WHAT LANDED. The model validator stays and now has two tests that construct an
entry directly: one substitutes a foreign action, one keeps the create action
but binds it to another address -- the sharper defect, because it names the
operation the operator expects and creates the wrong obligation. The controller
check stays, because model_copy remains a hole no model validator can close. The
gate is narrowed to an enumerated sanctioned mention carrying that reason.

Teeth on both branches of the narrowed gate: a new mention added to
navigation.py reds; removing every mention from the sanctioned file reds as
stale. The first stale attempt did NOT red, because I replaced one literal and
the file still carried another on the next line -- so the assertion was proven
only after the second, complete injection.

## Notes

The projector's own check is now the third copy of this rule. It raises
DeclarationsCalendarProjectionError where the model raises ValueError, so
removing it would change the exception type its callers see. That is a
behaviour change beyond this target and is left alone rather than folded in.
