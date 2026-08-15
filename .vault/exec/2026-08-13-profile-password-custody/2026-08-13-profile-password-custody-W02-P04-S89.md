---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:fe2fe50315a904c62c4240e3d76ea8e55ca047ada371fcfc9c6bb3396e912479'
step_id: 'S89'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the operator status projection report a verdict for an unregistered pointer

## Scope

- `src/cadrumo/application/auth/_operator.py and src/cadrumo/application/user_profile/`

## Description

- Stop the projection raising a raw storage error before any verdict is produced.
- Resolve the pointer through the authority the health assessment already uses.
- Establish whether one narrowing covers the sibling surfaces or whether they
  need separate edits.

## Outcome

The projection reports a verdict for an unregistered pointer instead of raising a
raw storage error from the engine guard. The health assessment it is built on
already declares a dangling-pointer status for exactly that state, so a
projection that raised defeated the assessment it exists to serve, and the
operator met it as the status verb refusing to run precisely when their profile
was broken.

**The seam chosen matters more than the raise avoided.** The projection now
resolves the pointer through the SAME resolver the health assessment uses, so a
projection and the verdict it carries cannot disagree about whether the pointer
resolves. Two independent answers to that question would have been fresh
fragmentation wearing the shape of a fix. When it does not resolve, the span
yields the stateless snapshot shape it already had, retaining the bucket
identifier so the verdict can still name it -- no new shape invented.

There was no test-side alternative, and that is what identified it as a
production defect rather than a stale test: seeding a capsule would make the
pointer registered and destroy the condition under test.

Verified independently: the module passes at 31, and the whole authority suite is
green.

## Notes

The question of whether one narrowing could cover all three affected surfaces was
answered by looking for it before writing three patches, and the answer is no for
a principled reason. The readiness probe raised an application-layer refusal;
this surface raises a storage-layer error one layer down during a workflow-state
load, so the application layer never sees a shared exception; and the revocation
case is a write path rather than a degradation at all. A single abstraction over
the first two would have to catch a storage-layer exception in the application
layer -- the boundary leak this project's grounding rule names -- and would
silently absorb genuine storage failures alongside the one benign case. Three
edits, each naming the shared cause, was the correct answer.

The shared cause is real but is a SYMPTOM description: surfaces raise where they
should answer. Treating that as a diagnosis is what would have produced the
single clever fix.

The commit for this step cites the wrong step identifier. It names `S88`, which
belongs to an unrelated row about a command-line lifecycle module, because the
author was dispatched with a swapped identifier and cited it faithfully. The
error is the dispatcher's: two rows were created in one batch, returned in
operation order, and re-paired by phase. The commit was not rewritten, since
amending a landed commit over concurrent work is disproportionate to a wrong
identifier, and this record is the correction.
