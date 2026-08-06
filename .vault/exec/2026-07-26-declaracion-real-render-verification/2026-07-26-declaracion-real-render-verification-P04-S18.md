---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:938a135393bd2db10682d1f3962f2b09c57c1013d25bec1e47fd1e5dcd2971ce'
step_id: 'S18'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Decide the disposition of verify_declaracion, a modelo-agnostic comparison mechanism with zero callers outside its own tests

## Scope

- `src/cadrumo/application/verification`

## Description

- Determine whether verify_declaracion is dead code, an unwired capability, or a deliberate seam.
- Establish it from the code and its history rather than from its docstring.
- Cross-check against the parallel audit already sitting in this feature.

## Outcome

An abandoned partial build. Not dead code, and not a deliberate seam.

The mechanism is real and modelo-agnostic, scoped by the same verification-policy fold the enrolled reconcile path uses, and it has no callers outside its own tests. The originating decision record planned it together with a CLI-wiring section naming two operator verbs. Neither verb was ever built, and the CLI root has since narrowed to two command families, so those names would not fit today even if someone wanted them.

The newer reconcile mechanism is not its replacement. It solves a different problem — comparing against a persisted revision, where this one computes fresh and needs no revision at all — and was enrolled months later. So the two are not duplicates and retiring one in favour of the other would lose a capability rather than remove a redundancy.

The practical consequence is that enrolling it today means designing a new operator verb under the current command vocabulary, not flipping a switch. That is a decision for whoever owns the CLI surface, and it is recorded here rather than taken.

## Notes

The finding was cross-checked against a parallel audit from another campaign that had reached the no-callers conclusion independently. Its claims reproduced, which is corroboration from a genuinely separate source rather than the citation loop this feature has had to break twice.

The disposition deliberately stops short of a recommendation to delete or to wire. Both are defensible and the choice depends on whether the fresh-compute capability is wanted, which is not this campaign's question.

## Decision, taken 2026-07-27

**Neither wired nor deleted. Declared.** The Step originally closed with a characterisation and no decision, which a consistency sweep caught, and reopening it produced a different answer than the first pass had reached.

The reachability finding was right and its framing was wrong. `verify_declaracion` has zero production *callers* and no entrypoint surface, which is what made "abandoned partial build" look correct. But three production modules cite it in their docstrings as the canonical statement of the scoping policy they implement -- the reconcile path and the casilla comparison both describe their own treatment by reference to it, as "the same policy verify_declaracion consumes" and "mirrors verify_declaracion's treatment".

So it is not dormant capability. It is an unwired **reference implementation** that documentation depends on, and nobody had said so. That is why it read as dead code: its current role was real and undeclared.

Deleting it would remove the definition three docstrings point at, leaving them citing nothing. Wiring it still requires designing an operator verb under a command vocabulary that has since narrowed, which is real work and not this campaign's. Both were the wrong question.

The disposition is to **declare the role it already has**: state in its own docstring that it is the reference implementation of the registry-declared reconciliation scope, that it is deliberately unwired, and that the enrolled reconcile path implements the same policy against a persisted revision where this one computes fresh. That makes it safe from a future dead-code sweep and makes the citation direction explicit. Tracked as its own Step.

Wiring remains available and is not foreclosed. What is foreclosed is deleting it as unreachable, which was the likely outcome of leaving it undeclared.
