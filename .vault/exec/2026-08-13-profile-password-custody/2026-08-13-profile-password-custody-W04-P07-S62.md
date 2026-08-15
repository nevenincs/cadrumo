---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:752935e1fbd44fb0986e9731545ed828abfb771f22ae67caac21e32824ee0329'
step_id: 'S62'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule which layer owns the bucket manifest

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py and src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py and src/cadrumo/tests/secure_sql.py`

## Description

- Rule which layer owns each fact the manifest carried, before touching a
  key-derivation path.
- Make the capsule the registration authority and prove the strand-risk guard
  survives.
- Delete the now-inert manifest write and migrate the tests that registered a
  bucket by writing one.

## Outcome

Registration is now resolved from the published capsule rather than from a file
nothing writes. The key-schedule enum declared exactly one member, so the
discriminator carried no information -- what it actually encoded was whether the
bucket is registered, and the capsule commit answers that definitively. The
session-lifetime facts have no writer at all and already degrade to the settings
defaults, so settings are their effective sole authority.

The load-bearing proof is the second of four arms. With the old lookup, a
REGISTERED bucket whose wrapped key had vanished silently MINTED a fresh key over
data it could no longer read; the bite proof restores that lookup from outside
the repository and the arm fails with a did-not-raise, which is exactly the
strand risk this ruling existed to protect. The guard now bites, and a future
change that loses it reds that test. Verified independently: four arms pass.

The inert manifest write in the shared test support was deleted in the same
change, and the retired-custody errors it was causing in the workflow suite are
gone.

## Notes

**The severity was WITHDRAWN by its own author, downward, and that correction is
the most important thing here.** The review had reported that every
capsule-published profile fails to open an ordinary session -- a claim this
dispatcher relayed. Instrumenting the real login path showed it SUCCEEDS against
a bucket with no manifest and never calls any of the manifest-backed helpers:
login authenticates the custody envelope directly, and session resume recovers
the key from the persisted record. The affected path was direct provider entry,
which has zero production invocations anywhere outside the adapter package that
defines it.

So the honest finding is much smaller: dead plumbing reachable only from test
helpers, whose practical effect was to force those helpers to pass an enrolment
flag production never passes. The coverage asymmetry survives intact -- the tests
were exercising a path no operator can reach -- but the product was not broken
for operators. Asking the narrowing question before signing off, and answering it
against the smaller claim, is what kept a dramatic and false statement out of the
record.

Making registration capsule-owned broke every test that registered a bucket by
writing a manifest, and those were migrated rather than left: the helpers now
publish a real capsule, bucket identifiers moved from labels to profile
identifiers because a non-identifier can never name a registered bucket, and two
stale assertions plus one test name were repointed at the property that now
holds. A previously-masked defect was fixed on the way, where a suite passed a
bucket identifier as a capsule label that the label validator refuses.

Measured against the true pre-change commit rather than a moving baseline: net
one FEWER failure in both affected suites, zero new red.

Two carry-forwards were deliberately declined. The session-lifetime manifest
reads are now permanently-fallback dead paths, but removing them ripples through
the forwarding port into the login session and belongs in its own commit rather
than riding a key-derivation change. And a remaining error set in the workflow
suite has now changed cause twice, ending at the capsule-publication collision
inside a widely-used fixture that still calls the retired directory provisioner --
which belongs to the conformance sweep row, not here.

Both halves of this work were swept into other campaigns' commits, and the
consequence was worse than misattribution: the production half landed WITHOUT the
test migration, so the main line sat red until a later sweep picked up the tests.
It surfaced only because a clean-baseline worktree returned this step's own
refusal message.
