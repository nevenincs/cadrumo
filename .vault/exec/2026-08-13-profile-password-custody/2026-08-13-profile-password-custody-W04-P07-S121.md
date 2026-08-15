---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:835748ff5987b02a52e364146270941206ae83e6807630f1ba316f10af84e647'
step_id: 'S121'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the bucket deletion assessment contract, since the fingerprint type is now producerless and its only consumer is the populated branch requiring label and fingerprint and retention together

## Scope

- `src/cadrumo/application/config_reset.py and src/cadrumo/application/bucket_maintenance/`

## Description

- Establish whether the unreachable populated branch is dead code or a
  specification awaiting its producer.
- Rule on whether to keep or remove it.

## Outcome

**Ruled: keep the contract, do not delete the branch. The reasoning behind that
ruling was wrong on the first attempt and is corrected below.**

The chain was measured end to end. The fingerprint type has zero production
constructions; the assessment's four exits are an absent-form result, two
refusals, and an unconditional raise exactly where the populated form would be
built; and the downstream target's populated correlation is therefore
unreachable too. Three models, one closed door.

**The first ruling read the producer's docstring — deferring to "a future
destructive command" — and concluded the branch was a specification awaiting
that command.** That was wrong. A producer for the same concept already existed
and was live, in the custody service's deletion preflight: a hold assessment
with real legal and filing evidence, an inventory digest, a pointer snapshot and
a bound confirmation. So this was never a missing producer. It was **two
preflight mechanisms for one concept**, with the orchestrator calling the dead
one at four sites while the working one sat in the same module, called once.

Had the first ruling been acted on, someone would have preserved a superseded
contract and then written a producer for it that duplicates the live preflight —
building the second implementation this campaign exists to remove, with a vault
record blessing it.

**What survives the correction is the conclusion, not the argument.** Do not
delete the branch as a first move — but because it is a supersession to be
executed rather than dead code to sweep, and because the old contract's fields
are the checklist for proving the new one covers everything before it goes. That
checklist then earned its place immediately: the supersession turned out to be
lossy, and the check is what caught it.

## Notes

**A deferral docstring is evidence about intent when it was written, never about
the present state of the tree.** The comment was not false and is not false now
about intent; it simply does not answer whether the future it names has already
arrived. Here it had, three modules away, under a different name — so searching
by MEANING for the replacement is what settles the question, while reading the
deferral only restates it.

The validators on the populated shape remain asserted by their author and
verified by nobody: they certify a state no production path has ever produced,
exercised only by a hand-built fixture. That caveat outlived both versions of
the ruling and is booked against the work that will finally produce that state,
so nobody reads a green suite as evidence the contract holds.
