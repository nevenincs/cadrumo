---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0cff22866b1641526e5b129a5e459a6ac524ddca42b6a171a8ce1c8034962bb3'
step_id: 'S49'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh resolve the collision between capsule publication and the workflow repository, and sweep every module still using that shape

## Scope

- `src/cadrumo/application/user_profile/ and src/cadrumo/application/workflow/ and src/cadrumo/application/modelo/tests/`

## Description

- Establish a clean baseline in a temporary worktree before judging anything,
  since the working tree carries several campaigns' uncommitted edits.
- Trace which party actually creates the contested directory, rather than
  assuming it is one of the two that report the disagreement.
- Give the bucket root a single creating authority and refuse every other
  creator.

## Outcome

The ruling is that NEITHER of the two disagreeing parties was wrong, and that is
the substance of this step. The capsule listing and the publication check are
asking different questions and both answer honestly: one asks whether a
committed capsule exists there, the other asks whether the path is free, and it
must ask that because the no-replace rename IS the atomicity primitive. The
wrong party was a third one outside both.

Opening a database engine for a bucket-routed location created the parent chain
with parents permitted, which walked up past the bucket boundary and conjured the
bucket root itself. Capsule publication then found its destination occupied. The
trace was made with a directory-creation wrapper applied from outside the
repository, not inferred from the error.

The fix is a single creating authority: creating directories WITHIN an already
published bucket still works, while creating a bucket root refuses with a named
storage error carrying the offending directory. This is grounded rather than
invented -- the accepted bucket-lifecycle decision states that the transaction
initialises the profile-local database inside the sibling staging capsule before
the single no-replace rename, and that there is no second post-publication
fact-store creation path. The engine was that second creator.

This also answers the ordering objection raised when the step was dispatched.
Seeding before reading was a convention every future author had to remember, and
demonstrably did not. With the production side fixed, forgetting it now produces
a precise refusal at the exact call site instead of a silent bucket enrolment
that surfaces later as an opaque destination conflict. The convention became an
enforced invariant.

Verified independently: 3 passed for the new regression, and the wider database
adapter suite green. The bite proof restores the permissive parent creation from
outside the repository and reds the refusal test.

## Notes

The two symptoms bundled into this row do NOT share a root cause, established
separately rather than assumed. The second, a retired-custody refusal across a
workflow suite, comes from a test helper writing a bucket manifest -- the exact
member the existence-only detector classifies as retired -- so the detector is
correct to refuse.

That second symptom was deliberately left unfixed, and the reasoning is the
reason to keep it visible: nothing in production writes that manifest any more,
but production still READS it to resolve a bucket's key schedule, idle window and
session cap. Two live authorities contradict each other. Removing the helper's
write would push every capsule-published bucket down a bootstrap branch that
mints a NEW key, which is precisely the key-derivation case this project treats
as owner-gated rather than autonomous, because it can strand encrypted data. It
is carried as its own row.

Forty-four modules still read workflow state before seeding. All were already
failing before this change; the fix substitutes a diagnostic early refusal for an
opaque late one at a one-to-one rate, adding no new red. Their repair is
mechanical and is carried separately.

The fix reached HEAD inside another campaign's commit about retiring the
recovery-phrase surface, which swept both working-tree files before this step
could commit them. Content is byte-identical and verified green, but the change
is not legible in history under its own description.
