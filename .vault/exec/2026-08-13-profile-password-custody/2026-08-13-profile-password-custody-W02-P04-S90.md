---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:6de5e848a97b957afce26db9cdf30f2051eb7c92845f69d01f041364e139f237'
step_id: 'S90'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the cold-pointer logout refusal name what it could not do and re-author the nine tests

## Scope

- `src/cadrumo/application/auth/_operator.py and src/cadrumo/application/auth/_operator_cleanup.py and src/cadrumo/application/auth/tests/test_operator_storage_session.py`

## Description

- Measure, from a cold pointer, which revocation operations actually require the
  key rather than reasoning about the ordering.
- Keep the refusal and make it name what did not happen and why.
- Re-author the nine tests around the enforced contract without relaxing any
  result assertion.

## Outcome

The refusal stays, and the reason is stronger than the one that was originally
approved. **Revoking the authority browser session genuinely requires the key**,
because that session is an encrypted secure-object row inside the bucket, so
deleting it means opening the bucket. Only lock-clearing is key-free, and
clearing a lock revokes nothing. A split logout would therefore have cleared
locks, revoked nothing, and returned a result the operator reads as logged out
while their session row sat intact on disk -- a mutation reporting success when
its precondition is false, built into the fix intended to remove that defect
class.

The dispatcher had approved that split, conditionally, on a premise measured from
the wrong artefact. The agent declined to implement it and measured each
operation from a cold pointer instead.

The separate question of whether anything GATES on the authentication stamps was
answered in full and turned out not to decide anything: nothing gates, every
consumer reports, and the one decision that could have gated -- whether to reuse
an existing session -- probes the real artefact and never consults the
workflow-state claim about it. So the stale-record danger was absent and the
value was absent too, which is why the refusal is right rather than merely safe.

The message tells the operator the fact they cannot otherwise discover: the
session is STILL LIVE. It names what did not happen, why, and the single command
that changes it, in all four catalogues, verified by probe rather than by
reading. It deliberately promises no route for an operator who cannot unlock,
because whether such a route exists is an open question elsewhere.

Verified independently: the whole authority suite is **344 passed, 0 failed** --
fully green for the first time in this campaign.

## Notes

Two design decisions inside the refusal are worth preserving. The narrowing wraps
ONLY the span's own entry refusal, so a refusal raised by the operation inside
the span keeps its own message rather than being silently relabelled by an
unguarded handler. And it covers the reset verb as well as logout, since reset
revokes the same encrypted row and carried the same misleading text.

**The verification of the re-authored tests is the strongest this campaign has
produced**, and it was demanded precisely because re-authoring a premise is how a
suite goes green for nothing. Two separate mutations from outside the repository:
neutering the revocation reds exactly the two tests asserting the revocation
happened, and removing the guard reds exactly one, the new contract test. Each
mutation reds what should react and leaves the rest alone. A single blanket red
would have shown only that something changed.

The cross-profile test needed the TARGET profile's session rather than the
caller's, because revoking one profile while only another is open is exactly what
the guard refuses -- so the re-authoring had to distinguish which profile is
unlocked, not merely unlock something.

The root cause of the wrong premise is carried as its own row: two artefacts,
the profile-session receipt in the keystore and the authority browser session
inside the bucket, are both called session while belonging to different custody
classes with different key requirements. A correct measurement of one was carried
onto the other by three readers across two rounds. Semantic grounding did not
protect against it -- it returned a confident, correct answer about the wrong
artefact.
