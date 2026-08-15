---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S123'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the persisted-format inventory detect an enrolled format whose code no longer exists

## Scope

- `src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Build a gate binding each inventory key to the module implementing it, so
  both directions of absence become checkable.
- Hold the undecided formats in a distinguishable state with the gap asserted
  as a count.
- Prove both directions bite from outside the repository.

## Outcome

The gate is green at eight passing, and both directions are proven. A key with
no live implementation reds; an implementation with no key reds. The blindness
that let a retired format keep a durable enrolment while the capsule holding the
password-wrapped key sat outside the inventory is now covered from both sides.

**The gate corrected its own author within seconds of existing.** Three inventory
keys had been recorded as carrying no version constant, confidently and
incorrectly -- they each carry one. That is the direction nothing had ever
checked, failing first on the person who built it, which is the strongest
possible first result. They are now bound rather than excused.

Sixteen formats are held in an explicit awaiting-classification state, separate
from exclusions, **with the count asserted so the gap is a number rather than a
silence**. The test states that the count moves down as each format is argued
and up only when a genuinely new one arrives unclassified, never to restore
green. A further check refuses any constant recorded as both excluded and
awaiting classification, because the two states only work while they stay
distinguishable -- collapsing them would let "nobody has looked at this" read as
"looked at and ruled out", which is the precise misreading that produced the
original gap.

Seventeen constants were moved into exclusions on arguable grounds: transport
schemas that never become a record on disk, domain shapes persisted inside an
already-enrolled secure object rather than as their own file, rebuildable
caches, namespace tokens naming an already-enrolled format rather than a second
one, a supported-version set and an unreadable-row sentinel. The remaining
sixteen were left unsorted rather than ranked by plausibility, which would have
been classification by another name.

## Notes

**A bite proof that passes is a bite proof that failed**, and this step is the
worked example. The first attempt at proving the implementation-without-key
direction PASSED, because pytest imports test modules through its own importer,
so patching the test module never took effect. The proof was accepted as a
failure rather than as a result, and the injection was moved down to the shared
AST inventory until it bit. The campaign's own standing note -- control-verify
that the neutering actually took effect -- is what caught it.

The anti-tautology test pinning that the walk sees an unannotated version
constant is the load-bearing one. That constant is how a name-based enumeration
missed an already-enrolled canonical tier while auditing enrolment, so the test
is the only thing standing between this gate and being rebuilt on the technique
that produced the class it catches.

One process failure worth recording. A first commit attempt reported nothing and
landed nothing, because the retry loop had redirected git's stderr and therefore
swallowed a held index lock. It was caught by reading the stat line and finding
a peer's commit where the author's should have been. **Silencing an error to
make a retry loop tidy is how a failure becomes invisible**, which is this
campaign's whole subject appearing in its own tooling.
