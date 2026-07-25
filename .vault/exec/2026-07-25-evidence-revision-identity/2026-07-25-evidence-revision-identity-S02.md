---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-26'
step_id: 'S02'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
---

# Gate that a discarded unit refuses at create and that the refusal names its state, closing the asymmetry where list_work_units hides a discarded unit by default while create_work_unit hands it back

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

Gate the refusal so it cannot silently regress, and gate it in both directions:
that a discarded unit refuses and names its state, and that the guard stays
narrow enough to leave idempotent re-creation of an ACTIVE unit intact.

The second half is the load-bearing one. A blanket refusal on any existing unit
would satisfy a naive refusal test while breaking the documented idempotent-create
contract, so the anti-vacuity case is what makes the rest of the module
trustworthy.

## Outcome

Landed in commit `4eed7f80f0` as
`application/modelo/tests/test_work_unit_discard_refusal.py`, five real-behaviour
tests over an isolated runtime profile and real repositories, no doubles.

The gate was proven able to fail rather than assumed to work. With HEAD content
restored in place of the guard, four of the five fail. The fifth —
the anti-vacuity test pinning that an ACTIVE unit still returns idempotently —
passes in both states, which is exactly its purpose: without it, a blanket
refusal on every existing unit would satisfy the other four while silently
breaking the documented idempotent-create contract. The file was copied aside and
restored byte-exactly rather than reverted through git.

The circular-message test pins the locale KEY rather than the prose, keeping it a
structural assertion while still catching a future author who routes this refusal
onto the generic mutation-refused message and reintroduces the circular
instruction.

A fifth test pins the asymmetry the defect rested on: the listing surface already
hid a discarded unit by default while creation handed it back, so discovery and
creation disagreed about whether it existed. They now agree, and the audit view
still returns it.

Gates: 1384 passed across `application/modelo` and `domain/modelos` with zero
failures; 61 passed on the locale parity, honesty and coverage-inventory gates;
ruff check and format clean; ty clean. Markers were passed explicitly as
`unit or integration` on every run, never the repo default, which deselects
integration-marked modules and can exit green having selected nothing.

## Notes

Three shared-worktree hazards were met and are worth recording.

The locale catalogues carried a peer's uncommitted censo work, so the change was
isolated at hunk level with a filter that refuses any hunk mixing foreign
lines rather than trusting a pathspec. A pathspec commit would have taken
working-tree content and swept the peer's keys.

An abandoned zero-byte `index.lock` blocked commits for roughly ten minutes. It
was diagnosed rather than removed on impatience: no process held it open, its
mtime postdated the last commit, and an exclusive-open test confirmed it was
crash residue rather than live contention before it was cleared.

A peer's broad commit then swept the four locale keys into its own SHA mid-flight.
That is recorded in the commit message rather than corrected, because correcting
it would require rewriting history.
