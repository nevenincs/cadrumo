---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ca7b17961cec595eae819e779d7b48aea0d41ad8ce2b3555ef327010097e6517'
step_id: 'S54'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium sequence the remaining auth-coverage restoration behind the capsule-publication collision rather than beside it

## Scope

- `src/cadrumo/tests/profile_capsule.py and src/cadrumo/application/auth/tests/`

## Description

- Hold the remaining auth-coverage restoration until the publication collision
  is ruled, rather than restoring against a constraint that might disappear.
- Withhold the shared seeding helper until the constraint's permanence is known.
- Re-rule both once the collision is resolved.

## Outcome

The sequencing held and the restoration was unparked, but NOT for the reason it
was ordered, and the difference is worth recording rather than smoothing over.

The hold was placed on the possibility that resolving the collision would REMOVE
the ordering constraint, which would have turned a shared seeding helper into
scaffolding built around a rule that no longer existed -- and a well-named helper
is harder to retire than an obviously ugly hand-copy, because it reads as
intended design. That possibility did not materialise. The constraint did not
vanish; it became enforced law, with an explicit refusal at the exact site naming
the bucket directory.

So the seed-before-read shape is not a workaround that survived its cause. It is
the correct usage of a contract the system now enforces, and the hand-copies that
looked like propagating scaffolding are simply early conformance. Nothing needs
unwinding.

That inverts the original ruling's premise while leaving its instruction intact:
waiting was right, the predicted reason was wrong. The decision was defensible
before the fact because the risk was asymmetric -- restoring three thousand four
hundred lines against a constraint that might evaporate is expensive to undo,
while waiting costs only time -- but it was not vindicated, and claiming
otherwise would misrepresent why the order was correct.

With permanence established, the condition set for the shared helper is met and
it is authorised: a named seeding helper in the shared capsule test support, with
the existing hand-copies folded into it. Thirty-four or more modules carrying an
ordering rule that lives only in per-file docstrings is the duplication this
campaign exists to remove, and the argument for tolerating it -- that the rule
might not last -- no longer applies.

The sequence is therefore: establish the population, land the helper, sweep the
existing modules onto it, then restore the ten outstanding auth modules against
it. That way the restored coverage is written against one canonical shape from
the start rather than re-deriving it per module.

## Notes

The conformance sweep is carried as its own row, as is the removal of a second
bucket-root creator that survives as dead production code.

A consequence to keep visible: enforcing the invariant turned roughly twenty-six
command-line test modules red. That is honest failure rather than regression --
they passed because production permitted a second bucket creator, and the
permission is gone. Nothing about the conformance work may soften the guard to
reduce that count.
