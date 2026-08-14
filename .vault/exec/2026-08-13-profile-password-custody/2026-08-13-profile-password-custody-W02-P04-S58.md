---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ba0e90dafa93967e7a1d141f96354aeff121ef92c9b41ff8f13d6a38798d1371'
step_id: 'S58'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the profile-record authority re-derive on liveness as well as identity

## Scope

- `src/cadrumo/application/user_profile/_profile_record_repository.py`

## Description

- Read the identity sibling's recorded reasoning before choosing an approach, since
  it explicitly ruled liveness out of its own scope and said why.
- Confirm the hazard by probing the real classes before changing anything.
- Give the closed test one definition rather than a second.

## Outcome

A retired authority is now treated exactly as an ABSENT one: re-derived where a
live custody session exists, refused cleanly where none does. Deliberately the
same shape as the identity sibling, so the two failure modes converge rather than
accumulating separate handling.

Reading the prior reasoning first was load-bearing rather than courtesy. The
earlier step KEPT the test helper's session retirement but narrowed its
justification to zeroising the key material the span unlocked, explicitly NOT to
a reachability claim. That zeroisation is precisely what manufactures this
hazard -- so deleting the retirement, which would have looked like removing a
redundant workaround, would have HIDDEN this defect instead of fixing it. Neither
edge was touched.

The hazard was confirmed by probe against the real classes before any change:
closing a session zeroises its key material in place and leaves the object
latched with its identity binding intact, so the same corpse is handed back for
the same profile, and using it raises an integrity error. The public surface
carries exactly one closed-ish member, the close method itself, which makes the
row's claim that there is no liveness predicate exact rather than approximate.

The predicate now has ONE definition. The closed test already existed inline
inside the key accessor; rather than adding a second, it moved onto the session
as a property the accessor reads. It is expressed as the ABSENCE of key material
rather than as a separate flag, so a future variant of close cannot forget to set
it. Verified: one definition, one read site.

Nothing is unbound on the refusing path, on the reasoning that a read which
declines should not mutate process state, and a later successful derivation
replaces the dead reference anyway.

Verified independently: 15 passed.

## Notes

The bite pair is opposite-direction, and the first attempt at the under-arm was
redone rather than accepted. That attempt patched the closed predicate itself, so
the test reddened at its own precondition rather than at the behaviour under
test -- a proof that fires for the wrong reason. Reverting the guard instead
makes the behavioural assertion the thing that fails. The over-arm, in which
every authority reports itself retired, is what pins the second test: a guard
re-deriving unconditionally would satisfy the retirement case while silently
abolishing the latch.

A new shared-worktree hazard surfaced during this step and is the inverse of the
one already known. Uncommitted production edits were silently DESTROYED by a
concurrent whole-file rewrite from another campaign's relocation series: the
change was made, verified by probe, and then the test run failed with a missing
attribute because both files had reverted to committed content -- with the
version-control status reporting them clean, which reads as though the edit was
never made. Previously landed work in the same area was checked and found intact;
only the in-flight edit was lost. The practical consequence is that a clean
status is not evidence an edit exists, and uncommitted production changes should
be held for the shortest possible window.

One cosmetic defect is deliberately not repaired: the commit message lost a word
to shell interpretation of backticks. Amending was declined because the commit
is no longer the tip, so the correction would require rewriting history over
peers' commits -- disproportionate to a message whose meaning survives.
